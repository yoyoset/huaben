import sqlite3

import pytest

from huaben import repo


def test_book_and_bible_roundtrip(conn):
    bid = repo.create_book(conn, "诡仙", "修仙恐怖")
    repo.update_book(conn, bid, synopsis="一个故事")
    repo.save_bible(conn, bid, world="灵气枯竭", characters=[{"name": "阿蘅"}], taboos=["现代梗"])
    b = repo.get_book(conn, bid)
    assert b["synopsis"] == "一个故事" and b["read_pos"] == 0
    bible = repo.get_bible(conn, bid)
    assert bible["characters"] == [{"name": "阿蘅"}]
    assert bible["taboos"] == ["现代梗"]
    assert bible["style_samples"] == []


def test_unknown_fields_rejected(conn):
    bid = repo.create_book(conn, "x")
    with pytest.raises(ValueError):
        repo.update_book(conn, bid, nope=1)
    with pytest.raises(ValueError):
        repo.save_bible(conn, bid, nope=1)


def test_volume_lifecycle_and_chapters(conn):
    bid = repo.create_book(conn, "x")
    vid = repo.create_volume(conn, bid, 1, goal="入门", beats=["a", "b"], status="active")
    assert repo.active_volume(conn, bid)["beats"] == ["a", "b"]
    assert repo.next_chapter_idx(conn, bid) == 1
    cid = repo.create_chapter(conn, bid, vid, 1, outline="o")
    repo.update_chapter(conn, cid, body="正文", summary="摘要", status="accepted")
    assert repo.next_chapter_idx(conn, bid) == 2
    assert [c["idx"] for c in repo.recent_chapters(conn, bid, 3)] == [1]
    repo.seal_volume(conn, vid, "卷摘要")
    assert repo.active_volume(conn, bid) is None
    assert repo.list_volumes(conn, bid)[0]["summary"] == "卷摘要"


def test_duplicate_chapter_idx_rejected(conn):
    bid = repo.create_book(conn, "x")
    vid = repo.create_volume(conn, bid, 1)
    repo.create_chapter(conn, bid, vid, 1)
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_chapter(conn, bid, vid, 1)


def test_buffered_ahead_counts_only_accepted_beyond_read_pos(conn):
    bid = repo.create_book(conn, "x")
    vid = repo.create_volume(conn, bid, 1)
    for i in range(1, 6):
        cid = repo.create_chapter(conn, bid, vid, i)
        repo.update_chapter(conn, cid, status="accepted" if i <= 4 else "written")
    assert repo.buffered_ahead(conn, bid) == 4
    repo.update_book(conn, bid, read_pos=2)
    assert repo.buffered_ahead(conn, bid) == 2


def test_ledger(conn):
    bid = repo.create_book(conn, "x")
    repo.upsert_character(conn, bid, "江烬", core=True, knows=["秘密"], updated_ch=1)
    repo.upsert_character(conn, bid, "江烬", alive=False, core=True, updated_ch=5)
    chars = repo.list_characters(conn, bid)
    assert len(chars) == 1 and chars[0]["alive"] is False and chars[0]["core"] is True
    fid = repo.add_foreshadow(conn, bid, 2, "玉佩发烫", "卷末揭示")
    repo.add_foreshadow(conn, bid, 3, "井里有声")
    repo.update_foreshadow(conn, fid, status="resolved", resolved_ch=9)
    assert len(repo.list_foreshadows(conn, bid)) == 2
    assert [f["content"] for f in repo.list_foreshadows(conn, bid, open_only=True)] == ["井里有声"]
    repo.add_fact(conn, bid, "太玄宗禁夜行", 1)
    assert repo.list_facts(conn, bid)[0]["fact"] == "太玄宗禁夜行"


def test_cost_summary(conn):
    bid = repo.create_book(conn, "x")
    repo.log_run(conn, bid, "write", chapter_idx=1, duration_ms=8000, tokens_in=3000, tokens_out=4000, cost_usd=0.01)
    repo.log_run(conn, bid, "ledger", chapter_idx=1, duration_ms=2000, cost_usd=0.002)
    repo.log_run(conn, bid, "write", chapter_idx=2, duration_ms=10000, cost_usd=0.012)
    s = repo.cost_summary(conn, bid)
    assert s["chapters"] == 2
    assert s["avg_cost_usd"] == pytest.approx(0.012)
    assert s["avg_ms"] == 10000


def test_cascade_delete_book(conn):
    bid = repo.create_book(conn, "x")
    vid = repo.create_volume(conn, bid, 1)
    repo.create_chapter(conn, bid, vid, 1)
    repo.add_fact(conn, bid, "f", 1)
    conn.execute("DELETE FROM books WHERE id=?", (bid,))
    assert conn.execute("SELECT COUNT(*) FROM chapters").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM ledger_facts").fetchone()[0] == 0
