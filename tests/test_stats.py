"""运行统计的口径:失败稿与卷级费用摊进单章成本;开书费用单列;耗时只算章级。"""
import pytest

from huaben import repo
from huaben.stats import book_stats


@pytest.fixture
def book(conn):
    bid = repo.create_book(conn, "x")
    vid = repo.create_volume(conn, bid, 1, status="active")
    for i, attempts in ((1, 1), (2, 3)):
        cid = repo.create_chapter(conn, bid, vid, i)
        repo.update_chapter(conn, cid, status="accepted", summary="s", attempts=attempts)
    repo.set_audio(conn, repo.get_chapter(conn, bid, 1)["id"], "basic", "a.mp3")
    log = lambda **kw: repo.log_run(conn, bid, **kw)  # noqa: E731
    log(step="write", chapter_idx=1, cost_usd=0.010, duration_ms=10_000, tokens_out=4000)
    log(step="write", chapter_idx=2, cost_usd=0.010, duration_ms=12_000, tokens_out=4000)
    log(step="check", chapter_idx=2, ok=False, note="contradiction: 复活")       # 打回
    log(step="write", chapter_idx=2, cost_usd=0.010, duration_ms=8_000, tokens_out=4000)  # 重写
    log(step="volume_plan", cost_usd=0.004, duration_ms=5_000)
    log(step="opening", cost_usd=0.002)
    log(step="finalize", cost_usd=0.003)
    log(step="tts", chapter_idx=2, ok=False, note="edge-tts timeout")
    return bid


def test_cost_includes_failed_drafts_and_volume_steps_not_opening(conn, book):
    s = book_stats(conn, book)
    assert s["chapters"] == 2
    assert s["avg_cost_usd"] == pytest.approx((0.030 + 0.004) / 2)
    assert s["total_cost_usd"] == pytest.approx(0.039)
    assert s["cost_breakdown_usd"] == pytest.approx({"chapter": 0.030, "volume": 0.004, "opening": 0.005})


def test_time_and_tokens_are_chapter_level(conn, book):
    s = book_stats(conn, book)
    assert s["avg_seconds"] == pytest.approx(15.0) and s["avg_tokens_out"] == 6000


def test_rewrites_audio_and_failures(conn, book):
    s = book_stats(conn, book)
    assert s["avg_attempts"] == 2 and s["rewrite_rate"] == 0.5 and s["voiced"] == 1
    assert s["failures"] == {"check": 1, "tts": 1}
    assert [f["step"] for f in s["recent_failures"]] == ["tts", "check"]  # 最新的在前


def test_empty_book_has_zeroes_not_division_errors(conn):
    s = book_stats(conn, repo.create_book(conn, "空"))
    assert s["chapters"] == 0 and s["avg_cost_usd"] == 0 and s["rewrite_rate"] == 0 and s["failures"] == {}


def test_editor_notes_are_surfaced_but_not_counted_as_failures(conn, book):
    """软观察写进运行记录、进统计(路线 67);它 ok=1,不能混进失败。"""
    repo.log_run(conn, book, "ledger", chapter_idx=2, note="编辑观察(未打回):招牌能力进阶要写成爽点")
    repo.log_run(conn, book, "ledger", chapter_idx=1, note="正常入账")  # 不是软观察,不该出现
    s = book_stats(conn, book)
    assert len(s["editor_notes"]) == 1
    assert s["editor_notes"][0]["chapter_idx"] == 2
    assert "编辑观察(未打回):" in s["editor_notes"][0]["note"]
    assert s["failures"].get("ledger") is None  # ok=1,不算失败
