"""书与故事圣经。"""
from ..db import dumps, loads
from ._util import row


def create_book(conn, title: str, genre: str = "", profile_id: int | None = None) -> int:
    cur = conn.execute("INSERT INTO books(title, genre, profile_id) VALUES (?, ?, ?)", (title, genre, profile_id))
    conn.execute("INSERT INTO bibles(book_id) VALUES (?)", (cur.lastrowid,))
    conn.commit()
    return cur.lastrowid


def open_chapter(conn, book_id: int, idx: int) -> bool:
    """读者打开/播放了第 idx 章:续读位置 = idx;最远进度只增不减。返回最远进度是否前进了。"""
    before = conn.execute("SELECT read_pos FROM books WHERE id=?", (book_id,)).fetchone()[0]
    conn.execute("UPDATE books SET last_opened=?, read_pos=MAX(read_pos, ?) WHERE id=?", (idx, idx, book_id))
    conn.commit()
    return idx > before


def get_book(conn, book_id: int) -> dict | None:
    return row(conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone())


def list_books(conn, profile_id: int | None = None) -> list[dict]:
    """profile_id=None:全部书(后台补货要巡检所有人的书);否则只取这个人的书架。"""
    if profile_id is None:
        return [dict(r) for r in conn.execute("SELECT * FROM books ORDER BY id")]
    return [dict(r) for r in conn.execute("SELECT * FROM books WHERE profile_id=? ORDER BY id", (profile_id,))]


def update_book(conn, book_id: int, *, commit: bool = True, **fields) -> None:
    allowed = {"title", "genre", "synopsis", "status", "read_pos", "last_opened", "gen_error", "audio_error", "craft"}
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
_BIBLE_SCALAR = {"world", "style_fingerprint", "canon", "extracted_msgs"}


def get_bible(conn, book_id: int) -> dict | None:
    r = row(conn.execute("SELECT * FROM bibles WHERE book_id=?", (book_id,)).fetchone())
    if r:
        for k in _BIBLE_JSON:
            r[k] = loads(r[k])
    return r


def save_bible(conn, book_id: int, *, commit: bool = True, **fields) -> None:
    bad = set(fields) - _BIBLE_JSON - _BIBLE_SCALAR
    if bad:
        raise ValueError(f"unknown bible fields: {bad}")
    if not fields:
        return
    vals = [dumps(v) if k in _BIBLE_JSON else v for k, v in fields.items()]
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE bibles SET {sets} WHERE book_id=?", (*vals, book_id))
    if commit:
        conn.commit()
