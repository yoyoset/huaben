"""读者(profile = 人)。每人一个书架;不做密码——家用,Tailscale 已挡住外人。"""
from ._util import row


def create_profile(conn, name: str) -> int:
    """重名抛 sqlite3.IntegrityError(名字就是家里人区分彼此的方式,不能重)。"""
    cur = conn.execute("INSERT INTO profiles(name) VALUES (?)", (name,))
    conn.commit()
    return cur.lastrowid


def get_profile(conn, profile_id: int) -> dict | None:
    return row(conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone())


def list_profiles(conn) -> list[dict]:
    """附带每人的书数,"谁在看"页面上显示。"""
    return [dict(r) for r in conn.execute(
        "SELECT p.*, (SELECT COUNT(*) FROM books b WHERE b.profile_id = p.id) AS books "
        "FROM profiles p ORDER BY p.id")]


def rename_profile(conn, profile_id: int, name: str) -> None:
    conn.execute("UPDATE profiles SET name=? WHERE id=?", (name, profile_id))
    conn.commit()
