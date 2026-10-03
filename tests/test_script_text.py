"""剧本制(四)导入正文(T016):存、覆盖、硬检查、写章时用导入稿。"""
import json

import pytest

from huaben import repo
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.pipeline.chapter import generate_chapter
from huaben.pipeline.errors import ChapterFailed
from huaben.script_import import ScriptImportError, import_book, import_volume
from huaben.script_text import import_chapter_texts
from scripted_llm import body_for
from test_script_import import BOOK
from test_script_volume import ScriptOnlyLLM, ch

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)


def _book_with_outlines(conn):
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    import_volume(conn, FakeLLM([]), S, bid, {
        "volume": {"goal": "入门", "beats": ["起"], "beat_chapters": [3]},
        "chapters": [ch(1), ch(2), ch(3)]})
    return bid


def _body(n, prefix=""):
    return f"（第{n}章{prefix}）" + body_for(n)


def test_import_and_overwrite(conn):
    bid = _book_with_outlines(conn)
    assert import_chapter_texts(conn, bid, [{"idx": 1, "body": _body(1)}, {"idx": 2, "body": _body(2)}]) == \
           {"saved": [1, 2]}
    assert repo.get_scripted_body(conn, bid, 1).startswith("（第1章）")
    import_chapter_texts(conn, bid, [{"idx": 1, "body": _body(1, prefix="改")}])
    assert repo.get_scripted_body(conn, bid, 1).startswith("（第1章改）")


def test_import_rejects_non_scripted_book(conn):
    bid = repo.create_book(conn, "普通")
    with pytest.raises(ScriptImportError, match="不是剧本书"):
        import_chapter_texts(conn, bid, [{"idx": 1, "body": "x" * 600}])


def test_import_rejects_chapter_without_outline_atomically(conn):
    bid = _book_with_outlines(conn)
    with pytest.raises(ScriptImportError, match="还没有剧本章纲"):
        import_chapter_texts(conn, bid, [{"idx": 1, "body": _body(1)}, {"idx": 9, "body": _body(2)}])
    assert repo.get_scripted_body(conn, bid, 1) is None  # 整批不存


def test_import_rejects_accepted_chapter(conn):
    bid = _book_with_outlines(conn)
    generate_chapter(conn, ScriptOnlyLLM(), S, bid)  # 第 1 章定稿
    with pytest.raises(ScriptImportError, match="已经定稿"):
        import_chapter_texts(conn, bid, [{"idx": 2, "body": _body(2)}, {"idx": 1, "body": _body(1)}])
    assert repo.get_scripted_body(conn, bid, 2) is None


def test_import_rejects_short_and_duplicate(conn):
    bid = _book_with_outlines(conn)
    with pytest.raises(ScriptImportError, match="不到"):
        import_chapter_texts(conn, bid, [{"idx": 1, "body": _body(1)}, {"idx": 2, "body": "太短"}])
    assert repo.get_scripted_body(conn, bid, 1) is None
    with pytest.raises(ScriptImportError, match="重复"):
        import_chapter_texts(conn, bid, [{"idx": 1, "body": _body(1)}, {"idx": 1, "body": _body(2)}])
    assert repo.get_scripted_body(conn, bid, 1) is None


def test_imported_text_is_used_verbatim_without_author_calls(conn):
    bid = _book_with_outlines(conn)
    import_chapter_texts(conn, bid, [{"idx": 1, "body": _body(1)}, {"idx": 2, "body": _body(2)}])
    llm = ScriptOnlyLLM()
    generate_chapter(conn, llm, S, bid)
    generate_chapter(conn, llm, S, bid)
    from huaben.pipeline.draft_check import clean_draft
    assert repo.get_chapter(conn, bid, 1)["body"] == clean_draft(_body(1))
    notes = [r[0] for r in conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE '%来自导入的正文%'")]
    assert len(notes) == 2
    assert not any("现在写第 1 章正文" in c or "现在写第 2 章正文" in c for c in llm.calls)
    generate_chapter(conn, llm, S, bid)  # 第 3 章没有导入正文,走原流程
    assert any("现在写第 3 章正文" in c for c in llm.calls)


def test_short_imported_text_only_warns(conn):
    bid = _book_with_outlines(conn)
    import_chapter_texts(conn, bid, [{"idx": 1, "body": _body(1)}])  # 约 700 字
    s = Settings(openrouter_api_key="x", chapter_words=2000, _env_file=None)
    ch = generate_chapter(conn, ScriptOnlyLLM(), s, bid)
    assert ch["status"] == "accepted"
    notes = [r[0] for r in conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE '%导入正文的提醒%'")]
    assert any("篇幅不足" in n for n in notes)  # 只留痕,不打回


def test_ledger_contradiction_only_warns(conn):
    bid = _book_with_outlines(conn)
    import_chapter_texts(conn, bid, [{"idx": 1, "body": _body(1)}])
    led = json.dumps({"summary": "s", "characters": [], "foreshadows_new": [], "foreshadows_update": [],
                      "facts": [], "contradictions": [{"what": "位置矛盾", "planned": False}]}, ensure_ascii=False)
    assert generate_chapter(conn, FakeLLM([led]), S, bid)["status"] == "accepted"
    notes = [r[0] for r in conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE '%出入(未打回)%'")]
    assert len(notes) == 1 and "位置矛盾" in notes[0]


def test_ledger_failure_twice_fails_loudly(conn):
    bid = _book_with_outlines(conn)
    import_chapter_texts(conn, bid, [{"idx": 1, "body": _body(1)}])
    with pytest.raises(ChapterFailed) as ei:
        generate_chapter(conn, FakeLLM(["坏", "坏"]), S, bid)
    assert ei.value.step == "ledger"


def test_import_texts_endpoint(tmp_path):
    from fastapi.testclient import TestClient

    from huaben.api.app import create_app
    from huaben.db import connect
    s = Settings(openrouter_api_key="x", data_dir=tmp_path, worker_enabled=False, _env_file=None)
    conn = connect(s.db_path)
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    import_volume(conn, FakeLLM([]), S, bid, {"volume": {"goal": "入门", "beats": ["起"], "beat_chapters": [1]},
                                              "chapters": [ch(1)]})
    c = TestClient(create_app(s))
    r = c.post(f"/api/books/{bid}/import/texts", json={"chapters": [{"idx": 1, "body": _body(1)}]})
    assert r.status_code == 200 and r.json() == {"saved": [1]}
    assert c.post(f"/api/books/{bid}/import/texts", json={"chapters": [{"idx": 1, "body": "短"}]}).status_code == 400
