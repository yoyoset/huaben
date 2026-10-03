"""人物志(路线 61):把账本人物现状整理成读者能读的一页。纯函数 + API。"""
from huaben import cast, repo
from huaben.pipeline.ledger_apply import apply_ledger
from huaben.pipeline.normalize import normalize_ledger

BIBLE = {"characters": [{"name": "沈砚之", "role": "主角", "traits": "腹黑"}]}


def test_build_orders_core_and_played_first_and_renders_signature():
    rows = [
        {"name": "路人甲", "alive": True, "core": False, "profile": "", "location": "", "abilities": "",
         "relations": "", "knows": [], "signature": {}, "updated_ch": 0},
        {"name": "沈砚之", "alive": True, "core": True, "profile": "账房之子", "location": "文昌阁",
         "abilities": "", "relations": "与苏见微互试", "knows": ["试题被泄", "赵元瑾是公主"],
         "signature": {"name": "算脉", "rule": "以神魂为算盘", "stage": "一算", "next": "三算"}, "updated_ch": 9},
    ]
    out = cast.build(rows, BIBLE)
    assert [c["name"] for c in out] == ["沈砚之", "路人甲"]  # 已登场/核心在前,没登场的沉底
    assert out[0]["role"] == "主角" and out[0]["signature_text"] == "算脉——以神魂为算盘;当前:一算;下一阶:三算"
    assert out[0]["knows"] == ["试题被泄", "赵元瑾是公主"]


def test_build_caps_known_list():
    rows = [{"name": "X", "alive": True, "core": False, "profile": "", "location": "", "abilities": "",
             "relations": "", "knows": [str(i) for i in range(10)], "signature": {}, "updated_ch": 1}]
    c = cast.build(rows)[0]
    assert len(c["knows"]) == cast.MAX_KNOWN and c["knows_more"] == 10 - cast.MAX_KNOWN
    assert c["signature_text"] == "" and c["signature"] == {}


def test_cast_endpoint_surfaces_signature(tmp_path):
    """端到端:账本里有招牌能力 → /cast 能把名字、阶段、关系读出来。"""
    from fastapi.testclient import TestClient

    from huaben.api.app import create_app
    from huaben.config import Settings
    from huaben.db import connect

    app = create_app(Settings(openrouter_api_key="x", data_dir=tmp_path, worker_enabled=False, _env_file=None))
    c = TestClient(app)
    bid = c.post("/api/books", json={"title": "书"}).json()["id"]
    conn = connect(app.state.settings.db_path)
    vid = repo.create_volume(conn, bid, 1, status="active")
    cid = repo.create_chapter(conn, bid, vid, 1)
    repo.upsert_character(conn, bid, "沈砚之", core=True, relations="与苏见微互试",
                          signature={"name": "算脉", "rule": "借灵数", "stage": "一算", "next": "三算"})
    repo.update_chapter(conn, cid, body="b")
    apply_ledger(conn, bid, cid, 1, normalize_ledger(
        {"summary": "s", "characters": [], "foreshadows_new": [], "foreshadows_update": [], "facts": [],
         "contradictions": []}))
    conn.close()
    body = c.get(f"/api/books/{bid}/cast").json()
    one = body["characters"][0]
    assert one["name"] == "沈砚之" and one["signature"]["name"] == "算脉"
    assert "三算" in one["signature_text"] and one["relations"] == "与苏见微互试"
