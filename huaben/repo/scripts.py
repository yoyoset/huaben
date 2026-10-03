"""剧本制:预先写好的章纲(scripted_outlines)与伏笔代号。"""
from ..db import dumps, loads


def save_scripted_outlines(conn, book_id: int, outlines: dict, commit: bool = True) -> None:
    """{章序号: 原始章纲 dict} 存进库(原样,含节奏标记与 plant.key)。同号覆盖。"""
    conn.executemany("INSERT OR REPLACE INTO scripted_outlines(book_id, idx, outline) VALUES (?,?,?)",
                     [(book_id, int(idx), dumps(o)) for idx, o in outlines.items()])
    if commit:
        conn.commit()


def get_scripted_outline(conn, book_id: int, idx: int) -> dict | None:
    r = conn.execute("SELECT outline FROM scripted_outlines WHERE book_id=? AND idx=?", (book_id, idx)).fetchone()
    return loads(r[0]) if r else None


def list_scripted_outlines(conn, book_id: int) -> list[dict]:
    return [loads(r[0]) for r in conn.execute(
        "SELECT outline FROM scripted_outlines WHERE book_id=? ORDER BY idx", (book_id,))]


def max_scripted_idx(conn, book_id: int) -> int:
    return conn.execute("SELECT COALESCE(MAX(idx),0) FROM scripted_outlines WHERE book_id=?", (book_id,)).fetchone()[0]


def foreshadow_ids_by_key(conn, book_id: int) -> dict[str, int]:
    return {r["key"]: r["id"] for r in conn.execute(
        "SELECT id, key FROM ledger_foreshadows WHERE book_id=? AND key != ''", (book_id,))}
