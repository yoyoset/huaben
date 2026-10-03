"""书架显示"已备稿、还没放出"的章数(T022):count_pending_bodies 与 book_view 的 pending_drafts。"""
from huaben import repo
from huaben.api.routes_books import book_view
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.script_import import import_book, import_volume
from huaben.script_text import import_chapter_texts
from scripted_llm import body_for
from test_script_import import BOOK
from test_script_volume import ch

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)


def _book_with_outlines_and_bodies(conn):
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    import_volume(conn, FakeLLM([]), S, bid, {
        "volume": {"goal": "入门", "beats": ["起"], "beat_chapters": [3]},
        "chapters": [ch(1), ch(2), ch(3)]})
    import_chapter_texts(conn, bid, [{"idx": i, "body": f"（第{i}章）" + body_for(i)} for i in (1, 2, 3)])
    return bid


def test_count_pending_bodies(conn):
    bid = _book_with_outlines_and_bodies(conn)
    assert repo.count_pending_bodies(conn, bid, 0) == 3
    assert repo.count_pending_bodies(conn, bid, 2) == 1
    assert repo.count_pending_bodies(conn, bid, 3) == 0


def test_book_view_pending_drafts(conn):
    bid = _book_with_outlines_and_bodies(conn)
    b = repo.get_book(conn, bid)
    assert book_view(conn, b, S)["pending_drafts"] == 3  # 一章都没定稿,3 章备稿全部挂起
    plain = repo.create_book(conn, "普通书")
    assert book_view(conn, repo.get_book(conn, plain), S)["pending_drafts"] == 0
