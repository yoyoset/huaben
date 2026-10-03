"""剧本制(一)导入书目(T010):book.json → 一本可连载的剧本书;真相层只存不用。"""
import json

import pytest

from huaben import repo
from huaben.config import Settings
from huaben.pipeline.errors import ChapterFailed
from huaben.pipeline.parsing import ParseError
from huaben.pipeline.volume import ensure_active_volume
from huaben.script_import import ScriptImportError, import_book

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)
MARKER = "XYZZY-真相标记"
BOOK = {
    "profile": "我",
    "craft": {"narrative": "linear", "prose": "literary", "imagination": "fresh", "foreshadow": "standard",
              "pacing": "balanced", "notes": "要好笑"},
    "bible": {
        "title": "夜行录", "genre": "古代恐怖", "synopsis": "少年夜巡人的故事。",
        "theme": "孤独与守望", "central_mystery": "井底的东西是什么", "world": "灵气枯竭的王朝",
        "characters": [
            {"name": "沈照", "role": "主角", "traits": "腹黑",
             "signature": {"name": "听风耳", "rule": "听见三里内的私语", "stage": "初开", "next": "辨心音"}},
            {"name": "阿蘅", "role": "药师", "traits": "冷"}],
        "core_characters": ["沈照"], "style_fingerprint": "短句,冷幽默", "taboos": ["现代梗"],
    },
    "style_samples": ["夜很长。"],
    "secrets": "真相:沈照是井底的守灵人。" + MARKER,
}


def test_import_book_creates_scripted_book(conn):
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    b = repo.get_book(conn, bid)
    assert b["scripted"] == 1 and b["status"] == "serializing" and b["title"] == "夜行录"
    bible = repo.get_bible(conn, bid)
    assert bible["world"] == "灵气枯竭的王朝" and bible["secrets"] == BOOK["secrets"]
    assert bible["style_samples"] == ["夜很长。"]
    chars = {c["name"]: c for c in repo.list_characters(conn, bid)}
    assert chars["沈照"]["core"] is True and chars["沈照"]["signature"]["name"] == "听风耳"
    assert chars["阿蘅"]["core"] is False
    from huaben.craft import from_book
    assert from_book(b)["notes"] == "要好笑"


def test_import_book_missing_profile_leaves_nothing(conn):
    with pytest.raises(ScriptImportError, match="读者"):
        import_book(conn, BOOK)
    assert repo.list_books(conn) == []


def test_import_book_missing_world_leaves_nothing(conn):
    repo.create_profile(conn, "我")
    with pytest.raises(ParseError):
        import_book(conn, {**BOOK, "bible": {**BOOK["bible"], "world": ""}})
    assert repo.list_books(conn) == []


def test_import_book_rejects_duplicate_title(conn):
    repo.create_profile(conn, "我")
    import_book(conn, BOOK)
    with pytest.raises(ScriptImportError, match="同名"):
        import_book(conn, BOOK)
    assert len(repo.list_books(conn)) == 1


def test_secrets_never_reach_prompts_or_reader_api(tmp_path):
    from fastapi.testclient import TestClient

    from huaben.api.app import create_app
    from huaben.context import load_context
    from huaben.db import connect
    from huaben.pipeline.prompts import ledger_messages, outline_messages, write_messages
    from huaben.pipeline.volume_prompts import plan_messages
    s = Settings(openrouter_api_key="x", data_dir=tmp_path, worker_enabled=False, _env_file=None)
    conn = connect(s.db_path)
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    outline = {"title": "T", "outline": "事", "characters": [], "foreshadows": [], "planned_reversals": [],
               "hook": "钩"}
    ctx = load_context(conn, bid)
    texts = [outline_messages(ctx)[1]["content"], write_messages(ctx, outline, 1000)[1]["content"],
             ledger_messages(ctx, outline, "正文")[1]["content"], plan_messages(ctx, 1)[1]["content"]]
    assert all(MARKER not in t for t in texts)
    c = TestClient(create_app(s))
    for path in (f"/api/books/{bid}", f"/api/books/{bid}/cast", f"/api/books/{bid}/foreshadows"):
        assert MARKER not in c.get(path).text


def test_scripted_book_without_volume_waits_for_script(conn):
    from huaben.llm_fake import FakeLLM
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    llm = FakeLLM([])
    with pytest.raises(ChapterFailed) as ei:
        ensure_active_volume(conn, llm, S, bid)
    assert ei.value.step == "script" and llm.calls == []  # 一条剧本都没有:不调模型去规划


def test_non_scripted_book_still_plans_a_volume(conn):
    from huaben.llm_fake import FakeLLM
    bid = repo.create_book(conn, "普通书")
    plan = json.dumps({"goal": "g", "beats": ["a"], "plant": [], "resolve": [], "target_chapters": 10},
                      ensure_ascii=False)
    assert ensure_active_volume(conn, FakeLLM([plan]), S, bid)["idx"] == 1


def test_import_book_endpoint(tmp_path):
    from fastapi.testclient import TestClient

    from huaben.api.app import create_app
    from huaben.db import connect
    s = Settings(openrouter_api_key="x", data_dir=tmp_path, worker_enabled=False, _env_file=None)
    conn = connect(s.db_path)
    repo.create_profile(conn, "我")
    c = TestClient(create_app(s))
    r = c.post("/api/import/book", json=BOOK)
    assert r.status_code == 200 and r.json()["book_id"] > 0
    assert c.post("/api/import/book", json={**BOOK, "profile": "不存在"}).status_code == 400
