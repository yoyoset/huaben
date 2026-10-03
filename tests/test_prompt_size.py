"""一次生成的 prompt 体量观测(路线 68):分层记忆应让长篇也保持在合理区间。"""
from huaben import repo
from huaben.config import Settings
from huaben.context import load_context
from huaben.prompt_size import WARN_CHARS, measure


def test_measure_reports_outline_and_write_sizes(conn):
    bid = repo.create_book(conn, "书")
    repo.create_volume(conn, bid, 1, status="active", target_chapters=30)
    ctx = load_context(conn, bid)
    m = measure(ctx, words=2500)
    assert m["outline_chars"] > 0 and m["write_chars"] > 0
    assert m["warn_chars"] == WARN_CHARS and m["too_long"] is False


def test_a_huge_canon_is_flagged_by_prompt_size(conn):
    """定本膨胀(封卷没去重)时,下一章 prompt 会超观测线并被告警——只观测,不截断。"""
    bid = repo.create_book(conn, "书")
    repo.save_bible(conn, bid, canon="设定条目很多。" * 8000)  # 48000 字,明显超过观测线
    repo.create_volume(conn, bid, 1, status="active")
    m = measure(load_context(conn, bid), words=2500)
    assert m["too_long"] is True and m["write_chars"] > WARN_CHARS


def test_stats_surfaces_prompt_size(tmp_path):
    from fastapi.testclient import TestClient

    from huaben.api.app import create_app

    app = create_app(Settings(openrouter_api_key="x", data_dir=tmp_path, worker_enabled=False, _env_file=None))
    c = TestClient(app)
    bid = c.post("/api/books", json={"title": "书"}).json()["id"]
    s = c.get(f"/api/books/{bid}/stats").json()
    assert s["prompt"]["write_chars"] > 0 and "too_long" in s["prompt"]
