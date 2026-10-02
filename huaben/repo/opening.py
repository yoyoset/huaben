"""开书对话记录。"""


def add_message(conn, book_id: int, role: str, content: str, commit: bool = True) -> None:
    conn.execute("INSERT INTO opening_messages(book_id, role, content) VALUES (?,?,?)", (book_id, role, content))
    if commit:
        conn.commit()


def list_messages(conn, book_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT role, content FROM opening_messages WHERE book_id=? ORDER BY id", (book_id,))]
