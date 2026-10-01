import json

import httpx
import pytest

from huaben.config import Settings
from huaben.llm import LLMEmptyError, LLMError, OpenRouterClient, build_payload, parse_response
from huaben.llm_fake import FakeLLM


def settings(**kw):
    return Settings(openrouter_api_key="sk-test", _env_file=None, **kw)


def ok_body(text="你好", finish="stop", cost=0.0021):
    return {"choices": [{"message": {"content": text}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 1200, "completion_tokens": 3400, "cost": cost}}


def client(handler, **kw):
    return OpenRouterClient(settings(), transport=httpx.MockTransport(handler),
                            sleep=lambda s: None, **kw)


def test_payload_follows_lessons():
    p = build_payload("m", [{"role": "user", "content": "x"}], max_tokens=8000, temperature=0.9)
    assert p["frequency_penalty"] == 0 and p["presence_penalty"] == 0
    assert p["reasoning"] == {"effort": "none"}
    assert p["max_tokens"] == 8000
    assert "response_format" not in p
    assert build_payload("m", [], max_tokens=1, temperature=0, json_mode=True)["response_format"]


def test_chat_success_and_request_shape():
    seen = {}

    def handler(req: httpx.Request):
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        seen["path"] = req.url.path
        return httpx.Response(200, json=ok_body())

    res = client(handler).chat([{"role": "user", "content": "写一章"}])
    assert res.text == "你好" and res.tokens_in == 1200 and res.tokens_out == 3400
    assert res.cost_usd == pytest.approx(0.0021) and not res.truncated
    assert seen["auth"] == "Bearer sk-test" and seen["path"].endswith("/chat/completions")
    assert seen["body"]["model"] == "deepseek/deepseek-v4.1-flash"
    assert seen["body"]["reasoning"] == {"effort": "none"}


def test_truncated_flag():
    res = client(lambda r: httpx.Response(200, json=ok_body(finish="length"))).chat([])
    assert res.truncated


def test_empty_content_retries_then_raises():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(200, json=ok_body(text="", finish="length"))

    with pytest.raises(LLMEmptyError):
        client(handler, retries=2).chat([])
    assert len(calls) == 3


def test_retry_on_5xx_then_succeed():
    responses = [httpx.Response(503, text="busy"), httpx.Response(429, text="slow"),
                 httpx.Response(200, json=ok_body())]
    res = client(lambda r: responses.pop(0)).chat([])
    assert res.text == "你好"


def test_4xx_not_retried():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(401, text="bad key")

    with pytest.raises(LLMError, match="401"):
        client(handler).chat([])
    assert len(calls) == 1


def test_network_error_retried_then_raised():
    def handler(req):
        raise httpx.ConnectTimeout("timeout")

    with pytest.raises(LLMError, match="network error"):
        client(handler, retries=1).chat([])


def test_error_body_shape():
    with pytest.raises(LLMError, match="boom"):
        parse_response({"error": {"message": "boom"}}, 1)


def test_missing_key_fails_fast():
    with pytest.raises(LLMError, match="API_KEY"):
        OpenRouterClient(Settings(openrouter_api_key="", _env_file=None))


def test_fake_llm_records_and_replays():
    f = FakeLLM(["a", RuntimeError("x")])
    assert f.chat([{"role": "user", "content": "q"}]).text == "a"
    with pytest.raises(RuntimeError):
        f.chat([])
    assert len(f.calls) == 2
