import json

import httpx
import pytest

from huaben.config import Settings
from huaben.llm import LLMEmptyError, LLMError, OpenRouterClient
from huaben.llm_responses import THINK_ROOM, build_responses_payload, parse_responses, uses_responses

MSGS = [{"role": "system", "content": "你是写手"}, {"role": "user", "content": "写一章"}]

SAMPLE = {
    "status": "completed",
    "incomplete_details": None,
    "output": [
        {"type": "reasoning", "status": "completed", "encrypted_content": "…", "summary": []},
        {"type": "message", "role": "assistant",
         "content": [{"type": "output_text", "text": "正文在这里", "annotations": [], "logprobs": []}]},
    ],
    "usage": {"input_tokens": 45, "output_tokens": 199, "total_tokens": 244,
              "output_tokens_details": {"reasoning_tokens": 126}},
}


def test_uses_responses():
    assert uses_responses("muse-spark-1.3-contributor")
    assert not uses_responses("deepseek-v4.1-flash")
    assert not uses_responses("mimo-v2.6-flash")
    assert not uses_responses("deepseek/deepseek-v4.1-flash")


def test_build_payload_shape():
    p = build_responses_payload("muse-spark-1.3-contributor", MSGS, max_tokens=6000, temperature=0.9)
    assert p["input"] == MSGS
    assert p["max_output_tokens"] == 8000 == 6000 + THINK_ROOM
    assert p["reasoning"] == {"effort": "minimal"}
    for k in ("messages", "max_tokens", "frequency_penalty", "presence_penalty", "reasoning_effort", "text"):
        assert k not in p


def test_build_payload_json_mode():
    p = build_responses_payload("m", MSGS, max_tokens=1, temperature=0, json_mode=True)
    assert p["text"] == {"format": {"type": "json_object"}}


def test_parse_sample():
    res = parse_responses(SAMPLE, 123)
    assert res.text == "正文在这里"
    assert res.tokens_in == 45 and res.tokens_out == 199
    assert res.truncated is False
    assert res.duration_ms == 123
    assert res.cost_usd == 0.0 and res.provider == ""


def test_parse_joins_messages_in_order():
    data = {
        "status": "completed",
        "output": [
            {"type": "message", "content": [
                {"type": "output_text", "text": "一"},
                {"type": "output_text", "text": "二"},
            ]},
            {"type": "message", "content": [{"type": "output_text", "text": "三"}]},
        ],
        "usage": {"input_tokens": 1, "output_tokens": 2},
    }
    assert parse_responses(data, 0).text == "一二三"


def test_parse_empty_raises_with_tokens():
    data = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
            "output": [], "usage": {"input_tokens": 58, "output_tokens": 2000}}
    with pytest.raises(LLMEmptyError) as ei:
        parse_responses(data, 0)
    assert ei.value.tokens_out == 2000
    assert "status=incomplete" in str(ei.value) and "output_tokens=2000" in str(ei.value)


def test_parse_truncated_with_text():
    data = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "半截"}]}],
            "usage": {"input_tokens": 1, "output_tokens": 2000}}
    res = parse_responses(data, 0)
    assert res.truncated is True and res.text == "半截"


def test_parse_bad_shape_raises():
    with pytest.raises(LLMError):
        parse_responses("oops", 0)


def settings(**kw):
    return Settings(openrouter_api_key="sk-test", _env_file=None, **kw)


def client(handler, **kw):
    return OpenRouterClient(settings(**kw), transport=httpx.MockTransport(handler), sleep=lambda s: None)


def test_client_uses_responses_endpoint():
    seen = {}

    def handler(req):
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)
        seen["session"] = req.headers.get("x-opencode-session")
        return httpx.Response(200, json=SAMPLE)

    res = client(handler, llm_model="muse-spark-1.3-contributor").chat(MSGS)
    assert res.text == "正文在这里"
    assert seen["path"].endswith("/responses")
    assert "input" in seen["body"] and "messages" not in seen["body"]
    assert seen["session"]


def test_client_other_models_keep_chat_endpoint():
    seen = {}

    def handler(req):
        seen["path"] = req.url.path
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 1, "completion_tokens": 1}})

    assert client(handler, llm_model="deepseek-v4.1-flash").chat(MSGS).text == "ok"
    assert seen["path"].endswith("/chat/completions")
