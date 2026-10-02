"""账本:人物现状、伏笔、世界事实。"""
from ..db import dumps, loads


def upsert_character(conn, book_id: int, name: str, *, alive=True, location="", abilities="",
                     relations="", knows=None, core=False, updated_ch=0, commit: bool = True) -> None:
    conn.execute(
        "INSERT INTO ledger_characters(book_id,name,alive,location,abilities,relations,knows,core,updated_ch) "
        "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(book_id,name) DO UPDATE SET "
        "alive=excluded.alive, location=excluded.location, abilities=excluded.abilities, "
        "relations=excluded.relations, knows=excluded.knows, core=excluded.core, updated_ch=excluded.updated_ch",
        (book_id, name, int(alive), location, abilities, relations, dumps(knows or []), int(core), updated_ch),
    )
    if commit:
        conn.commit()


def list_characters(conn, book_id: int) -> list[dict]:
    out = []
    for r in conn.execute("SELECT * FROM ledger_characters WHERE book_id=? ORDER BY core DESC, name", (book_id,)):
        d = dict(r)
        d["alive"] = bool(d["alive"])
        d["core"] = bool(d["core"])
        d["knows"] = loads(d["knows"])
        out.append(d)
    return out


def add_foreshadow(conn, book_id: int, planted_ch: int, content: str, payoff_plan: str = "", commit: bool = True) -> int:
    cur = conn.execute(
        "INSERT INTO ledger_foreshadows(book_id,planted_ch,content,payoff_plan) VALUES (?,?,?,?)",
        (book_id, planted_ch, content, payoff_plan),
    )
    if commit:
        conn.commit()
    return cur.lastrowid


def update_foreshadow(conn, fid: int, *, status: str, resolved_ch: int | None = None, commit: bool = True) -> None:
    conn.execute("UPDATE ledger_foreshadows SET status=?, resolved_ch=? WHERE id=?", (status, resolved_ch, fid))
    if commit:
        conn.commit()


def list_foreshadows(conn, book_id: int, open_only: bool = False) -> list[dict]:
    q = "SELECT * FROM ledger_foreshadows WHERE book_id=?"
    if open_only:
        q += " AND status != 'resolved'"
    return [dict(r) for r in conn.execute(q + " ORDER BY planted_ch, id", (book_id,))]


def add_fact(conn, book_id: int, fact: str, established_ch: int, commit: bool = True) -> int | None:
    """同一本书里一字不差的事实只记一次(重复登记会把真正新的事实挤出 prompt)。重复时返回 None。"""
    if conn.execute("SELECT 1 FROM ledger_facts WHERE book_id=? AND fact=?", (book_id, fact)).fetchone():
        return None
    cur = conn.execute(
        "INSERT INTO ledger_facts(book_id,fact,established_ch) VALUES (?,?,?)", (book_id, fact, established_ch)
    )
    if commit:
        conn.commit()
    return cur.lastrowid


def list_facts(conn, book_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM ledger_facts WHERE book_id=? ORDER BY established_ch, id", (book_id,))]
