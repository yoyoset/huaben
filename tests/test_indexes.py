"""路线 63:热路径查询用上索引(此前一张索引都没有,几全表扫描)。"""
from huaben import repo
from huaben.db import connect
from huaben.migrate import migrate


def test_hot_path_indexes_exist(conn):
    names = {r[1] for r in conn.execute("SELECT * FROM sqlite_master WHERE type='index'")}
    for n in ("idx_chapters_book_status", "idx_chapters_book_status_idx", "idx_runs_book_created",
              "idx_foreshadows_book_status", "idx_facts_book_ch", "idx_messages_book", "idx_audio_chapter"):
        assert n in names, f"缺索引 {n}"


def test_count_and_buffer_queries_use_an_index(tmp_path):
    """计数/缓冲判断/封卷范围此前是全表扫描:EXPLAIN 里应出现 USING INDEX,不再是 SCAN chapters。"""
    conn = connect(tmp_path / "h.db")
    migrate(conn)
    bid = repo.create_book(conn, "x")
    vid = repo.create_volume(conn, bid, 1, status="active")
    for i in range(1, 6):
        repo.create_chapter(conn, bid, vid, i)  # 建行即可
    conn.execute("UPDATE chapters SET status='accepted'")
    conn.commit()
    plans = []
    for sql, args in [
        ("SELECT COUNT(*) FROM chapters WHERE book_id=? AND status='accepted'", (bid,)),
        ("SELECT COUNT(*) FROM chapters c JOIN books b ON b.id=c.book_id "
         "WHERE c.book_id=? AND c.status='accepted' AND c.idx > b.read_pos", (bid,)),
        ("SELECT MAX(idx) FROM chapters WHERE book_id=? AND status='accepted'", (bid,)),
    ]:
        plans.append(" ".join(str(r[3]) for r in conn.execute("EXPLAIN QUERY PLAN " + sql, args)))
    assert all("INDEX" in p and "SCAN chapters" not in p for p in plans), plans
