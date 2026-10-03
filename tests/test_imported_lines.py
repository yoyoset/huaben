"""导入的正文也查章纲的"原话"与"结尾"(T023):只留痕,不打回(导入稿没有重写这一步)。"""
from huaben import repo
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.pipeline.chapter import generate_chapter
from huaben.script_import import import_book, import_volume
from huaben.script_text import import_chapter_texts
from scripted_llm import ScriptedLLM, body_for
from test_script_import import BOOK
from test_script_volume import ch

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)


def _import(conn, outline_extra: dict, body: str) -> dict:
    """导入书 → 1 章章纲(ch() 不支持 lines/ending,拿到字典后自己加)→ 导入正文 → 生成。"""
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    chapter = ch(1)
    chapter.update(outline_extra)
    import_volume(conn, FakeLLM([]), S, bid, {"volume": {"goal": "入门", "beats": ["起"], "beat_chapters": [1]},
                                              "chapters": [chapter]})
    import_chapter_texts(conn, bid, [{"idx": 1, "body": body}])
    return generate_chapter(conn, ScriptedLLM(), S, bid)


def _notes(conn) -> list[str]:
    return [r[0] for r in
            conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE '%导入正文的提醒(未打回)%'")]


def test_imported_text_missing_line_only_warns(conn):
    ch1 = _import(conn, {"lines": ["我不跑了。"]}, "（第1章）" + body_for(1))
    assert ch1["status"] == "accepted"
    assert any("我不跑了。" in n for n in _notes(conn))


def test_imported_text_missing_ending_only_warns(conn):
    ch1 = _import(conn, {"ending": "他站起来了。"}, "（第1章）" + body_for(1))
    assert ch1["status"] == "accepted"
    assert any("他站起来了。" in n for n in _notes(conn))


def test_imported_text_with_line_and_ending_warns_nothing(conn):
    body = "（第1章）" + body_for(1) + "我不跑了。他站起来了。"
    ch1 = _import(conn, {"lines": ["我不跑了。"], "ending": "他站起来了。"}, body)
    assert ch1["status"] == "accepted"
    assert not any("原样写出" in n or "指定的结尾" in n for n in _notes(conn))
