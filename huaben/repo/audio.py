"""章节音频记录(保底 basic / v1 高质量 hq)。"""
from ._util import row


def set_audio(conn, chapter_id: int, quality: str, path: str, duration_s: float | None = None) -> None:
    conn.execute(
        "INSERT INTO audio(chapter_id, quality, path, duration_s) VALUES (?,?,?,?) "
        "ON CONFLICT(chapter_id, quality) DO UPDATE SET path=excluded.path, duration_s=excluded.duration_s",
        (chapter_id, quality, path, duration_s),
    )
    conn.commit()


def get_audio(conn, chapter_id: int, quality: str = "basic") -> dict | None:
    return row(conn.execute("SELECT * FROM audio WHERE chapter_id=? AND quality=?", (chapter_id, quality)).fetchone())


def chapters_missing_audio(conn, book_id: int, quality: str = "basic") -> list[dict]:
    """已定稿但还没有指定质量音频的章,按章序。"""
    rows = conn.execute(
        "SELECT c.* FROM chapters c LEFT JOIN audio a ON a.chapter_id=c.id AND a.quality=? "
        "WHERE c.book_id=? AND c.status='accepted' AND a.chapter_id IS NULL ORDER BY c.idx",
        (quality, book_id),
    ).fetchall()
    return [dict(r) for r in rows]


def voiced_chapters(conn, book_id: int, quality: str = "basic") -> list[dict]:
    """已登记音频的定稿章(章的全部列 + audio_path)。用来核对文件是否真的还在。"""
    rows = conn.execute(
        "SELECT c.*, a.path AS audio_path FROM chapters c JOIN audio a ON a.chapter_id=c.id AND a.quality=? "
        "WHERE c.book_id=? AND c.status='accepted' ORDER BY c.idx", (quality, book_id)).fetchall()
    return [dict(r) for r in rows]
