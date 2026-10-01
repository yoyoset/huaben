"""章。"""
from ._util import row


def next_chapter_idx(conn, book_id: int) -> int:
    """下一个要写的章序号 = 已定稿章的最大序号 + 1。失败/半成品章不占号,避免序号出现空洞。"""
    r = conn.execute(
        "SELECT COALESCE(MAX(idx),0)+1 FROM chapters WHERE book_id=? AND status='accepted'", (book_id,)
    ).fetchone()
    return r[0]


def discard_unaccepted(conn, book_id: int) -> int:
    """清掉上次中断/失败留下的半成品章(失败原因已记在 pipeline_runs),返回清掉几章。"""
    cur = conn.execute("DELETE FROM chapters WHERE book_id=? AND status != 'accepted'", (book_id,))
    conn.commit()
    return cur.rowcount


def create_chapter(conn, book_id: int, volume_id: int, idx: int, outline: str = "", title: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO chapters(book_id, volume_id, idx, outline, title) VALUES (?,?,?,?,?)",
        (book_id, volume_id, idx, outline, title),
    )
    conn.commit()
    return cur.lastrowid


def get_chapter(conn, book_id: int, idx: int) -> dict | None:
    return row(conn.execute("SELECT * FROM chapters WHERE book_id=? AND idx=?", (book_id, idx)).fetchone())


def update_chapter(conn, chapter_id: int, *, commit: bool = True, **fields) -> None:
    allowed = {"outline", "title", "body", "summary", "status", "attempts"}
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"unknown chapter fields: {bad}")
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE chapters SET {sets} WHERE id=?", (*fields.values(), chapter_id))
    if commit:
        conn.commit()


def accepted_chapters(conn, book_id: int, volume_id: int | None = None) -> list[dict]:
    q, args = "SELECT * FROM chapters WHERE book_id=? AND status='accepted'", [book_id]
    if volume_id is not None:
        q += " AND volume_id=?"
        args.append(volume_id)
    return [dict(r) for r in conn.execute(q + " ORDER BY idx", args)]


def recent_chapters(conn, book_id: int, n: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM chapters WHERE book_id=? AND status='accepted' ORDER BY idx DESC LIMIT ?",
        (book_id, n),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def buffered_ahead(conn, book_id: int) -> int:
    """已就绪(accepted)但读者还没读到的章数,用来决定要不要继续预生成。"""
    r = conn.execute(
        "SELECT COUNT(*) FROM chapters c JOIN books b ON b.id=c.book_id "
        "WHERE c.book_id=? AND c.status='accepted' AND c.idx > b.read_pos", (book_id,)
    ).fetchone()
    return r[0]
