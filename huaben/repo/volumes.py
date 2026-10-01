"""卷。"""
from ..db import dumps, loads
from ._util import row


def create_volume(conn, book_id: int, idx: int, goal: str = "", beats=None,
                  plant=None, resolve=None, status: str = "planned", target_chapters: int = 30,
                  commit: bool = True) -> int:
    cur = conn.execute(
        "INSERT INTO volumes(book_id, idx, goal, beats, plant, resolve, status, target_chapters) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (book_id, idx, goal, dumps(beats or []), dumps(plant or []), dumps(resolve or []), status, target_chapters),
    )
    if commit:
        conn.commit()
    return cur.lastrowid


def _vol(r) -> dict | None:
    d = row(r)
    if d:
        for k in ("beats", "plant", "resolve"):
            d[k] = loads(d[k])
    return d


def get_volume(conn, volume_id: int) -> dict | None:
    return _vol(conn.execute("SELECT * FROM volumes WHERE id=?", (volume_id,)).fetchone())


def list_volumes(conn, book_id: int) -> list[dict]:
    return [_vol(r) for r in conn.execute("SELECT * FROM volumes WHERE book_id=? ORDER BY idx", (book_id,))]


def active_volume(conn, book_id: int) -> dict | None:
    return _vol(conn.execute(
        "SELECT * FROM volumes WHERE book_id=? AND status='active' ORDER BY idx LIMIT 1", (book_id,)
    ).fetchone())


def seal_volume(conn, volume_id: int, summary: str, commit: bool = True) -> None:
    conn.execute("UPDATE volumes SET status='sealed', summary=? WHERE id=?", (summary, volume_id))
    if commit:
        conn.commit()


def set_volume_status(conn, volume_id: int, status: str) -> None:
    conn.execute("UPDATE volumes SET status=? WHERE id=?", (status, volume_id))
    conn.commit()
