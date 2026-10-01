"""LLM 客户端(OpenRouter,OpenAI 兼容 chat/completions)。

默认值来自前身踩坑(docs/lessons-from-sillytavern.md):
- 长文生成 frequency/presence penalty 必须为 0(否则后半段标点消失)
- 显式发 reasoning.effort = "none"(思考模型会把 max_tokens 烧在思考上,正文为空)
- 正文为空 / 被截断要显式报错,不能让上层以为成功
"""
import time
from dataclasses import dataclass
from typing import Callable, Protocol

import httpx

from .config import Settings


class LLMError(Exception):
    """调用失败(网络/HTTP/响应格式)。"""


class LLMEmptyError(LLMError):
    """200 但正文为空(典型:思考吃光 max_tokens)。"""


@dataclass
class LLMResult:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    truncated: bool = False  # finish_reason == "length":正文被 max_tokens 截断


class LLM(Protocol):
    def chat(self, messages: list[dict], *, max_tokens: int | None = None,
             temperature: float = 0.9, json_mode: bool = False) -> LLMResult: ...


def build_payload(model: str, messages: list[dict], *, max_tokens: int, temperature: float,
                  json_mode: bool = False) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "reasoning": {"effort": "none"},
        "usage": {"include": True},  # OpenRouter 在 usage.cost 里返回真实费用
    }
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
    if not text.strip():
        raise LLMEmptyError(
            f"empty content (finish_reason={choice.get('finish_reason')}, "
            f"completion_tokens={usage.get('completion_tokens')})"
        )
    return LLMResult(
        text=text,
        tokens_in=int(usage.get("prompt_tokens") or 0),
        tokens_out=int(usage.get("completion_tokens") or 0),
        cost_usd=float(usage.get("cost") or 0.0),
        duration_ms=duration_ms,
        truncated=choice.get("finish_reason") == "length",
    )


_RETRY_STATUS = {408, 429, 500, 502, 503, 504}


class OpenRouterClient:
    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None,
                 retries: int = 2, sleep: Callable[[float], None] = time.sleep):
        if not settings.openrouter_api_key:
            raise LLMError("HUABEN_OPENROUTER_API_KEY 未配置")
        self._s = settings
        self._retries = retries
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=settings.openrouter_base_url,
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            timeout=settings.llm_timeout_s,
            transport=transport,
        )

    def chat(self, messages: list[dict], *, max_tokens: int | None = None,
             temperature: float = 0.9, json_mode: bool = False) -> LLMResult:
        payload = build_payload(self._s.llm_model, messages,
                                max_tokens=max_tokens or self._s.chapter_max_tokens,
                                temperature=temperature, json_mode=json_mode)
        last: Exception | None = None
        for attempt in range(self._retries + 1):
            if attempt:
                self._sleep(2 ** attempt)
            t0 = time.monotonic()
            try:
                r = self._http.post("/chat/completions", json=payload)
            except httpx.TransportError as e:  # 超时/连接失败:可重试
                last = LLMError(f"network error: {type(e).__name__}: {e}")
                continue
            if r.status_code in _RETRY_STATUS:
                last = LLMError(f"HTTP {r.status_code}: {r.text[:200]}")
                continue
            if r.status_code >= 400:  # 4xx(鉴权/参数)重试无意义,直接抛
                raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
            try:
                data = r.json()
            except ValueError as e:
                raise LLMError(f"non-JSON response: {r.text[:200]}") from e
            try:
                return parse_response(data, int((time.monotonic() - t0) * 1000))
            except LLMEmptyError as e:  # 空正文偶发:同样重试
                last = e
                continue
        raise last or LLMError("unknown failure")

    def close(self) -> None:
        self._http.close()
