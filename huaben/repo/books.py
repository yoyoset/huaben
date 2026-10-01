"""书与故事圣经。"""
from ..db import dumps, loads
from ._util import row


def create_book(conn, title: str, genre: str = "") -> int:
    cur = conn.execute("INSERT INTO books(title, genre) VALUES (?, ?)", (title, genre))
    conn.execute("INSERT INTO bibles(book_id) VALUES (?)", (cur.lastrowid,))
    conn.commit()
    return cur.lastrowid


def get_book(conn, book_id: int) -> dict | None:
    return row(conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone())


def list_books(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM books ORDER BY id")]


def update_book(conn, book_id: int, *, commit: bool = True, **fields) -> None:
    allowed = {"title", "genre", "synopsis", "status", "read_pos", "gen_error"}
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"unknown book fields: {bad}")
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE books SET {sets} WHERE id=?", (*fields.values(), book_id))
    if commit:
        conn.commit()


_BIBLE_JSON = {"characters", "style_samples", "taboos"}
_BIBLE_TEXT = {"world", "style_fingerprint"}


def get_bible(conn, book_id: int) -> dict | None:
    r = row(conn.execute("SELECT * FROM bibles WHERE book_id=?", (book_id,)).fetchone())
    if r:
        for k in _BIBLE_JSON:
            r[k] = loads(r[k])
    return r


def save_bible(conn, book_id: int, *, commit: bool = True, **fields) -> None:
    bad = set(fields) - _BIBLE_JSON - _BIBLE_TEXT
    if bad:
        raise ValueError(f"unknown bible fields: {bad}")
    if not fields:
        return
    vals = [dumps(v) if k in _BIBLE_JSON else v for k, v in fields.items()]
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE bibles SET {sets} WHERE book_id=?", (*vals, book_id))
    if commit:
        conn.commit()
