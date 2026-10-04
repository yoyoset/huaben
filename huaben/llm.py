"""LLM 客户端(OpenRouter,OpenAI 兼容 chat/completions)。

默认值来自前身踩坑(docs/lessons-from-sillytavern.md):
- 长文生成 frequency/presence penalty 必须为 0(否则后半段标点消失)
- 显式关思考(思考模型会把 max_tokens 烧在思考上,正文为空):OpenRouter 发 reasoning.effort,别家发 reasoning_effort
- 正文为空 / 被截断要显式报错,不能让上层以为成功
"""
import hashlib
import time
from dataclasses import dataclass
from typing import Callable, Protocol

import httpx

from . import __version__
from .config import Settings
from .llm_config import is_openrouter


class LLMError(Exception):
    """调用失败。kind 是给"人话错误"用的分类,不必解析消息文本:
    no_key / auth / quota / rate_limit / server / network / timeout / request / bad_response / empty
    """

    def __init__(self, message: str, kind: str = "bad_response", status: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status = status
        # 失败也可能已经计费(典型:200 但正文为空,token 照扣)。记下来,让 pipeline_runs 与花费上限看得见
        self.tokens_in = self.tokens_out = 0
        self.cost_usd = 0.0


def _http_kind(status: int) -> str:
    if status in (401, 403):
        return "auth"
    if status == 402:
        return "quota"
    if status == 429:
        return "rate_limit"
    if status == 408 or status >= 500:
        return "server"
    return "request"  # 其它 4xx:请求本身有问题(模型名错、参数不被接受)


class LLMEmptyError(LLMError):
    """200 但正文为空(典型:思考吃光 max_tokens)。"""

    def __init__(self, message: str, tokens_in: int = 0, tokens_out: int = 0, cost_usd: float = 0.0):
        super().__init__(message, kind="empty")
        self.tokens_in, self.tokens_out, self.cost_usd = tokens_in, tokens_out, cost_usd


@dataclass
class LLMResult:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    truncated: bool = False  # finish_reason == "length":正文被 max_tokens 截断
    provider: str = ""       # 实际出结果的托管商(OpenRouter 才有):质量/速度问题要能追到是哪一家


class LLM(Protocol):
    def chat(self, messages: list[dict], *, max_tokens: int | None = None,
             temperature: float = 0.9, json_mode: bool = False) -> LLMResult: ...


def build_payload(model: str, messages: list[dict], *, max_tokens: int, temperature: float,
                  json_mode: bool = False, openrouter: bool = True) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "frequency_penalty": 0,
        "presence_penalty": 0,
    }
    if openrouter:  # OpenRouter 扩展字段;别家(如 OpenCode Zen)可能把未知参数当错误拒绝,不发
        payload["reasoning"] = {"effort": "none"}
        payload["usage"] = {"include": True}  # OpenRouter 在 usage.cost 里返回真实费用
        # 只用 fp8 及以上精度的托管商,按速度排序。OpenRouter 默认先走最便宜的,而最便宜的几家是 fp4 量化:
        # 2026-10-02 实测同一真实章节 prompt,Decart(fp4)388 秒、DeepInfra(fp8)30 秒;生产第 1 章后半段
        # 整段无标点并转成繁体。贵的部分每章不到 0.1 美分。
        payload["provider"] = {"quantizations": ["fp8", "fp16", "bf16", "fp32"], "sort": "throughput"}
    else:
        # 别家用 OpenAI 标准字段关思考。2026-10-02 实测 OpenCode 的 deepseek-v4.1-flash:不发时 400 个输出 token
        # 全烧在思考上、正文为空;发 reasoning_effort="none" 后思考 0 token、正文正常;发 OpenRouter 的 reasoning 字段被 400 拒绝。
        payload["reasoning_effort"] = "none"
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    return payload


def parse_response(data: dict, duration_ms: int) -> LLMResult:
    try:
        choice = data["choices"][0]
        text = (choice.get("message") or {}).get("content") or ""
    except (KeyError, IndexError, TypeError) as e:
        err = data.get("error") if isinstance(data, dict) else None
        raise LLMError(f"unexpected response shape: {err or data!r}"[:500]) from e
    usage = data.get("usage") or {}
    tin, tout = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
    cost = float(usage.get("cost") or 0.0)
    if not text.strip():
        raise LLMEmptyError(
            f"empty content (finish_reason={choice.get('finish_reason')}, completion_tokens={tout})", tin, tout, cost)
    return LLMResult(text=text, tokens_in=tin, tokens_out=tout, cost_usd=cost, duration_ms=duration_ms,
                     truncated=choice.get("finish_reason") == "length", provider=str(data.get("provider") or ""))


_RETRY_STATUS = {408, 429, 500, 502, 503, 504}


def session_id(model: str, messages: list[dict]) -> str:
    """x-opencode-session:OpenCode Go 拒收不带它的请求(2026-10-02 实测 MissingSessionID),文档要求"每个对话一个稳定的号",
    服务商据此路由并做提示词缓存。我们的"对话"= 同一本书的同一类步骤:系统提示(圣经、样章)对一本书是稳定的,
    所以按 模型 + 系统提示 取哈希——同一本书连续写几十章都落在同一个会话上、共享缓存。纯函数;对别家服务商无害。"""
    system = messages[0]["content"] if messages and messages[0].get("role") == "system" else ""
    return hashlib.sha1(f"{model}|{system}".encode()).hexdigest()[:32]


class OpenRouterClient:
    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None,
                 retries: int = 2, sleep: Callable[[float], None] = time.sleep):
        if not settings.openrouter_api_key:
            raise LLMError("模型密钥未配置(网页「设置」或 HUABEN_OPENROUTER_API_KEY)", kind="no_key")
        self._s = settings
        self._retries = retries
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=settings.openrouter_base_url,
            # OpenCode Go 要求客户端用自己的 UA 如实自报(不用通用 HTTP 库名);会话号见 session_id
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}",
                     "User-Agent": f"huaben/{__version__} (personal serial-novel app)"},
            timeout=settings.llm_timeout_s,
            transport=transport,
        )

    def chat(self, messages: list[dict], *, max_tokens: int | None = None,
             temperature: float = 0.9, json_mode: bool = False) -> LLMResult:
        from .llm_responses import chat_request  # 函数体内导入:llm_responses 反过来要用本模块的 build_payload/parse_response
        path, payload, parse = chat_request(self._s.llm_model, messages,
                                            max_tokens=max_tokens or self._s.chapter_max_tokens,
                                            temperature=temperature, json_mode=json_mode,
                                            openrouter=is_openrouter(self._s.openrouter_base_url))
        last: LLMError | None = None
        wasted = LLMResult(text="")  # 被丢弃但已计费的尝试(空正文):计入最终结果或最终错误,不能凭空消失
        started = time.monotonic()
        deadline = started + self._s.llm_call_deadline_s
        for attempt in range(self._retries + 1):
            if attempt:
                self._sleep(min(2 ** attempt, max(deadline - time.monotonic(), 0)))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break  # 总时长耗尽:不再发起新的一次尝试
            # 单次 httpx 超时是"两字节之间",上游发保活字节永不触发;再套一个"这次尝试最多等到 deadline"的上限
            timeout = min(self._s.llm_timeout_s, remaining)
            t0 = time.monotonic()
            try:
                r = self._http.post(path, json=payload, timeout=timeout,
                                    headers={"x-opencode-session": session_id(self._s.llm_model, messages)})
            except httpx.TransportError as e:  # 超时/连接失败:可重试
                last = LLMError(f"network error: {type(e).__name__}: {e}", kind="network")
                continue
            if r.status_code in _RETRY_STATUS:
                last = LLMError(f"HTTP {r.status_code}: {r.text[:200]}", _http_kind(r.status_code), r.status_code)
                continue
            if r.status_code >= 400:  # 4xx(鉴权/参数)重试无意义,直接抛
                raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}", _http_kind(r.status_code), r.status_code)
            try:
                data = r.json()
            except ValueError as e:
                raise LLMError(f"non-JSON response: {r.text[:200]}") from e
            try:
                res = parse(data, int((time.monotonic() - t0) * 1000))
            except LLMEmptyError as e:  # 空正文偶发:同样重试,但它的费用要留着
                wasted.tokens_in += e.tokens_in
                wasted.tokens_out += e.tokens_out
                wasted.cost_usd += e.cost_usd
                last = e
                continue
            res.tokens_in += wasted.tokens_in
            res.tokens_out += wasted.tokens_out
            res.cost_usd += wasted.cost_usd
            return res
        if last is None or time.monotonic() >= deadline:
            # 总时长耗尽(或在耗尽前没有任何一次可重试的失败):显式报超时,而不是伪装成网络错误
            err = last if isinstance(last, LLMEmptyError) else LLMError(
                f"call deadline exceeded after {time.monotonic() - started:.0f}s", kind="timeout")
            err.tokens_in, err.tokens_out, err.cost_usd = wasted.tokens_in, wasted.tokens_out, wasted.cost_usd
            raise err
        err = last
        err.tokens_in, err.tokens_out, err.cost_usd = wasted.tokens_in, wasted.tokens_out, wasted.cost_usd
        raise err

    def close(self) -> None:
        self._http.close()
