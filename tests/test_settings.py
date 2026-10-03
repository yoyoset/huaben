"""网页「设置」(2026-10-02 用户要求:网页里填 key,以后换成 OpenCode 的 key)。"""
import json

import httpx
from fastapi.testclient import TestClient

from huaben.api.app import create_app
from huaben.api.deps import ensure_llm
from huaben.config import Settings
from huaben.llm import build_payload
from huaben.llm_config import effective, is_openrouter, key_tail, validate

OK = {"choices": [{"message": {"content": "收到"}, "finish_reason": "stop"}],
      "usage": {"prompt_tokens": 9, "completion_tokens": 2, "cost": 0.00001}}


def app_and_client(tmp_path, transport=None):
    s = Settings(openrouter_api_key="", data_dir=tmp_path, worker_enabled=False, _env_file=None)
    app = create_app(s)
    app.state.llm_transport = transport
    return app, TestClient(app)


def test_page_values_override_env_but_blank_ones_do_not():
    s = Settings(openrouter_api_key="env-key", _env_file=None)
    e = effective(s, {"api_key": "page-key", "base_url": "https://opencode.ai/zen/v1", "model": ""})
    assert (e.openrouter_api_key, e.openrouter_base_url, e.llm_model) == \
        ("page-key", "https://opencode.ai/zen/v1", s.llm_model)


def test_openrouter_only_fields_are_not_sent_elsewhere():
    assert is_openrouter("https://openrouter.ai/api/v1") and not is_openrouter("https://opencode.ai/zen/v1")
    p = build_payload("m", [], max_tokens=10, temperature=0, openrouter=False)
    assert "reasoning" not in p and "usage" not in p and p["frequency_penalty"] == 0 and p["presence_penalty"] == 0
    assert p["reasoning_effort"] == "none"  # 实测:OpenCode 不发这个就把输出全烧在思考上,正文为空
    assert build_payload("m", [], max_tokens=10, temperature=0)["reasoning"] == {"effort": "none"}


def test_helpers():
    assert key_tail("sk-or-v1-abcdef1234") == "…1234" and key_tail("") == "" and key_tail("short") == "已设置"
    assert validate({"base_url": "opencode.ai"}) and validate({"model": " "}) and validate({"model": "x"}) is None


def test_key_goes_in_never_comes_out_and_takes_effect_without_restart(tmp_path):
    app, c = app_and_client(tmp_path)
    assert c.get("/api/settings").json()["key_set"] is False
    assert c.get("/api/health").json()["llm"]["configured"] is False
    r = c.put("/api/settings", json={"api_key": "sk-secret-abcd9876", "base_url": "https://opencode.ai/zen/v1",
                                    "model": "deepseek-v4.1-flash"})
    body = r.json()
    assert body["key_tail"] == "…9876" and body["preset"] == "opencode" and body["key_from"] == "page"
    for page in (r.text, c.get("/api/settings").text, c.get("/api/health").text):
        assert "sk-secret-abcd9876" not in page
    assert c.get("/api/health").json()["llm"]["configured"] is True
    client = ensure_llm(app.state)._llm  # 守卫包着的真实客户端,按页面上的新配置建
    assert client._s.openrouter_base_url == "https://opencode.ai/zen/v1" and client._s.llm_model == "deepseek-v4.1-flash"


def test_blank_key_on_save_keeps_the_old_one(tmp_path):
    app, c = app_and_client(tmp_path)
    c.put("/api/settings", json={"api_key": "sk-first-11112222"})
    assert c.put("/api/settings", json={"api_key": "", "model": "x/y"}).json()["key_tail"] == "…2222"
    assert c.put("/api/settings", json={"base_url": "ftp://x"}).status_code == 400


def test_connection_check_reports_success_and_plain_language_failure(tmp_path):
    sent = []

    def handler(req):
        sent.append(json.loads(req.content))
        return httpx.Response(200, json=OK) if "good" in req.headers["authorization"] else httpx.Response(401, text="no")

    app, c = app_and_client(tmp_path, httpx.MockTransport(handler))
    c.put("/api/settings", json={"api_key": "sk-good-12345678", "base_url": "https://opencode.ai/zen/v1"})
    ok = c.post("/api/settings/test").json()
    assert ok["ok"] is True and ok["reply"] == "收到"
    assert "reasoning" not in sent[-1]  # 发给 OpenCode 的请求不带 OpenRouter 扩展字段
    c.put("/api/settings", json={"api_key": "sk-bad-87654321"})
    bad = c.post("/api/settings/test").json()
    assert bad["ok"] is False and "密钥无效" in bad["error"]


def test_openrouter_requests_avoid_fp4_hosts_and_record_who_served():
    """2026-10-02 实测:默认路由先走最便宜的 fp4 托管商,同一章节 prompt 388 秒(fp8 的 DeepInfra 30 秒)。"""
    p = build_payload("m", [], max_tokens=10, temperature=0)
    assert "fp4" not in p["provider"]["quantizations"] and p["provider"]["sort"] == "throughput"
    assert "provider" not in build_payload("m", [], max_tokens=10, temperature=0, openrouter=False)
    from huaben.llm import parse_response
    res = parse_response({**OK, "provider": "DeepInfra"}, 5)
    assert res.provider == "DeepInfra"


def test_requests_identify_themselves_for_opencode_go():
    """OpenCode Go 不带 x-opencode-session 直接拒(MissingSessionID),文档要求"每个对话一个稳定的号"、用自己的 UA。
    同一本书(系统提示相同)连续调用落在同一个会话上,好让服务商复用提示词缓存;换一本书就是另一个会话。"""
    import httpx
    from huaben.llm import OpenRouterClient
    seen = []

    def handler(req):
        seen.append(req.headers)
        return httpx.Response(200, json={"choices": [{"message": {"content": "好"}, "finish_reason": "stop"}]})
    st = Settings(openrouter_api_key="k", openrouter_base_url="https://opencode.ai/zen/go/v1", _env_file=None)
    c = OpenRouterClient(st, transport=httpx.MockTransport(handler))
    book_a = [{"role": "system", "content": "圣经甲"}, {"role": "user", "content": "第1章"}]
    c.chat(book_a)
    c.chat([book_a[0], {"role": "user", "content": "第2章"}])
    c.chat([{"role": "system", "content": "圣经乙"}, {"role": "user", "content": "第1章"}])
    assert seen[0]["user-agent"].startswith("huaben/")
    ids = [h["x-opencode-session"] for h in seen]
    assert ids[0] and ids[0] == ids[1] != ids[2]


def test_subscription_billing_is_not_reported_as_unreliable():
    """Go 是包月:上游不报费用(cost=0),不能因此一直提示"实际花费可能更高"。"""
    from huaben.budget import spend_status
    from huaben.llm_config import is_subscription
    assert is_subscription("https://opencode.ai/zen/go/v1") and not is_subscription("https://opencode.ai/zen/v1")
    assert not is_subscription("https://openrouter.ai/api/v1")
    s = spend_status(0.0, 2.0, 0.0, unpriced_calls=40, subscription=True)
    assert s["reliable"] and not s["over_remind"] and s["billing"] == "subscription"
    assert not spend_status(0.0, 2.0, 0.0, unpriced_calls=40)["reliable"]
