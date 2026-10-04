"""只走 /responses 接口的模型(Muse Spark)的请求构造与响应解析。纯函数,不发请求。

2026-10-04 在生产服务器上实测(带 x-opencode-session 头):
- muse-spark-1.3-contributor 的 /chat/completions 返回 400 ModelProtocolUnsupported,/responses 返回 200。
- 它关不掉思考:reasoning.effort 发 "none" 被 400 拒绝,只能发 minimal/low/medium/high/xhigh/max;
  不发默认 high(两句话烧了 1892 个思考 token),发 minimal 是 126 个。思考 token 算在 max_output_tokens 里。
"""
from .llm import LLMEmptyError, LLMError, LLMResult, build_payload, parse_response

THINK_ROOM = 2000  # 思考 token 算在 max_output_tokens 里,给它留的余量


def uses_responses(model: str) -> bool:
    """这个模型是不是只能走 /responses。目前只有 Muse 一家:模型名以 "muse-" 开头。"""
    return model.startswith("muse-")


def build_responses_payload(model, messages, *, max_tokens, temperature, json_mode=False) -> dict:
    payload = {
        "model": model,
        "input": messages,
        "max_output_tokens": max_tokens + THINK_ROOM,
        "temperature": temperature,
        "reasoning": {"effort": "minimal"},
    }
    if json_mode:
        payload["text"] = {"format": {"type": "json_object"}}
    return payload


def parse_responses(data: dict, duration_ms: int) -> LLMResult:
    if not isinstance(data, dict) or not isinstance(data.get("output"), list):
        raise LLMError(f"unexpected response shape: {data!r}"[:500])
    text = "".join(
        c.get("text") or ""
        for item in data["output"] if isinstance(item, dict) and item.get("type") == "message"
        for c in (item.get("content") or []) if isinstance(c, dict) and c.get("type") == "output_text"
    )
    usage = data.get("usage") or {}
    tin, tout = int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
    status = data.get("status")
    truncated = status == "incomplete" and (data.get("incomplete_details") or {}).get("reason") == "max_output_tokens"
    if not text.strip():
        raise LLMEmptyError(f"empty content (status={status}, output_tokens={tout})", tin, tout, 0.0)
    return LLMResult(text=text, tokens_in=tin, tokens_out=tout, cost_usd=0.0, duration_ms=duration_ms,
                     truncated=truncated, provider="")


def chat_request(model, messages, *, max_tokens, temperature, json_mode, openrouter):
    """OpenRouterClient.chat 用:返回(请求路径, 请求体, 解析函数)。
    只能走 /responses 的模型(Muse Spark)用 Responses 协议,其余照旧 chat/completions。"""
    if uses_responses(model):
        return ("/responses",
                build_responses_payload(model, messages, max_tokens=max_tokens,
                                        temperature=temperature, json_mode=json_mode),
                parse_responses)
    return ("/chat/completions",
            build_payload(model, messages, max_tokens=max_tokens, temperature=temperature,
                          json_mode=json_mode, openrouter=openrouter),
            parse_response)
