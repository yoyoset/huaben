"""数据访问:所有读写入口。流水线/API 不直接写 SQL。"""
import sqlite3

from .db import dumps, loads


def _row(r: sqlite3.Row | None) -> dict | None:
    return dict(r) if r is not None else None


# ---- 书 / 圣经 ----

def create_book(conn, title: str, genre: str = "") -> int:
    cur = conn.execute("INSERT INTO books(title, genre) VALUES (?, ?)", (title, genre))
    conn.execute("INSERT INTO bibles(book_id) VALUES (?)", (cur.lastrowid,))
    conn.commit()
    return cur.lastrowid


def get_book(conn, book_id: int) -> dict | None:
    return _row(conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone())


def list_books(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM books ORDER BY id")]


def update_book(conn, book_id: int, **fields) -> None:
    allowed = {"title", "genre", "synopsis", "status", "read_pos"}
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"unknown book fields: {bad}")
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE books SET {sets} WHERE id=?", (*fields.values(), book_id))
    conn.commit()


_BIBLE_JSON = {"characters", "style_samples", "taboos"}
_BIBLE_TEXT = {"world", "style_fingerprint"}


def get_bible(conn, book_id: int) -> dict | None:
    r = _row(conn.execute("SELECT * FROM bibles WHERE book_id=?", (book_id,)).fetchone())
    if r:
        for k in _BIBLE_JSON:
            r[k] = loads(r[k])
    return r


def save_bible(conn, book_id: int, **fields) -> None:
    bad = set(fields) - _BIBLE_JSON - _BIBLE_TEXT
    if bad:
        raise ValueError(f"unknown bible fields: {bad}")
    if not fields:
        return
    vals = [dumps(v) if k in _BIBLE_JSON else v for k, v in fields.items()]
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE bibles SET {sets} WHERE book_id=?", (*vals, book_id))
    conn.commit()


# ---- 卷 ----

def create_volume(conn, book_id: int, idx: int, goal: str = "", beats=None,
                  plant=None, resolve=None, status: str = "planned") -> int:
    cur = conn.execute(
        "INSERT INTO volumes(book_id, idx, goal, beats, plant, resolve, status) VALUES (?,?,?,?,?,?,?)",
        (book_id, idx, goal, dumps(beats or []), dumps(plant or []), dumps(resolve or []), status),
    )
    conn.commit()
    return cur.lastrowid


def _vol(r) -> dict | None:
    d = _row(r)
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


def seal_volume(conn, volume_id: int, summary: str) -> None:
    conn.execute("UPDATE volumes SET status='sealed', summary=? WHERE id=?", (summary, volume_id))
    conn.commit()


def set_volume_status(conn, volume_id: int, status: str) -> None:
    conn.execute("UPDATE volumes SET status=? WHERE id=?", (status, volume_id))
    conn.commit()


# ---- 章 ----

def next_chapter_idx(conn, book_id: int) -> int:
    r = conn.execute("SELECT COALESCE(MAX(idx),0)+1 FROM chapters WHERE book_id=?", (book_id,)).fetchone()
    return r[0]


def create_chapter(conn, book_id: int, volume_id: int, idx: int, outline: str = "", title: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO chapters(book_id, volume_id, idx, outline, title) VALUES (?,?,?,?,?)",
        (book_id, volume_id, idx, outline, title),
    )
    conn.commit()
    return cur.lastrowid


def get_chapter(conn, book_id: int, idx: int) -> dict | None:
    return _row(conn.execute("SELECT * FROM chapters WHERE book_id=? AND idx=?", (book_id, idx)).fetchone())


def update_chapter(conn, chapter_id: int, **fields) -> None:
    allowed = {"outline", "title", "body", "summary", "status", "attempts"}
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"unknown chapter fields: {bad}")
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE chapters SET {sets} WHERE id=?", (*fields.values(), chapter_id))
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


# ---- 账本 ----

def upsert_character(conn, book_id: int, name: str, *, alive=True, location="", abilities="",
                     relations="", knows=None, core=False, updated_ch=0) -> None:
    conn.execute(
        "INSERT INTO ledger_characters(book_id,name,alive,location,abilities,relations,knows,core,updated_ch) "
        "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(book_id,name) DO UPDATE SET "
        "alive=excluded.alive, location=excluded.location, abilities=excluded.abilities, "
        "relations=excluded.relations, knows=excluded.knows, core=excluded.core, updated_ch=excluded.updated_ch",
        (book_id, name, int(alive), location, abilities, relations, dumps(knows or []), int(core), updated_ch),
    )
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


def add_foreshadow(conn, book_id: int, planted_ch: int, content: str, payoff_plan: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO ledger_foreshadows(book_id,planted_ch,content,payoff_plan) VALUES (?,?,?,?)",
        (book_id, planted_ch, content, payoff_plan),
    )
    conn.commit()
    return cur.lastrowid


def update_foreshadow(conn, fid: int, *, status: str, resolved_ch: int | None = None) -> None:
    conn.execute("UPDATE ledger_foreshadows SET status=?, resolved_ch=? WHERE id=?", (status, resolved_ch, fid))
    conn.commit()


def list_foreshadows(conn, book_id: int, open_only: bool = False) -> list[dict]:
    q = "SELECT * FROM ledger_foreshadows WHERE book_id=?"
    if open_only:
        q += " AND status != 'resolved'"
    return [dict(r) for r in conn.execute(q + " ORDER BY planted_ch, id", (book_id,))]


def add_fact(conn, book_id: int, fact: str, established_ch: int) -> int:
    cur = conn.execute(
        "INSERT INTO ledger_facts(book_id,fact,established_ch) VALUES (?,?,?)", (book_id, fact, established_ch)
    )
    conn.commit()
    return cur.lastrowid


def list_facts(conn, book_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM ledger_facts WHERE book_id=? ORDER BY established_ch, id", (book_id,))]


# ---- 可观测 ----

def log_run(conn, book_id: int, step: str, *, chapter_idx: int | None = None, duration_ms: int = 0,
            tokens_in: int = 0, tokens_out: int = 0, cost_usd: float = 0.0, ok: bool = True, note: str = "") -> None:
    conn.execute(
        "INSERT INTO pipeline_runs(book_id,chapter_idx,step,duration_ms,tokens_in,tokens_out,cost_usd,ok,note) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (book_id, chapter_idx, step, duration_ms, tokens_in, tokens_out, cost_usd, int(ok), note),
    )
    conn.commit()


def cost_summary(conn, book_id: int) -> dict:
    """单章平均成本与耗时(v0 验收要求记录)。"""
    r = conn.execute(
        "SELECT COUNT(DISTINCT chapter_idx) AS chapters, COALESCE(SUM(cost_usd),0) AS cost, "
        "COALESCE(SUM(duration_ms),0) AS ms, COALESCE(SUM(tokens_in),0) AS tin, COALESCE(SUM(tokens_out),0) AS tout "
        "FROM pipeline_runs WHERE book_id=? AND chapter_idx IS NOT NULL", (book_id,)
    ).fetchone()
    n = r["chapters"] or 0
    return {
        "chapters": n, "total_cost_usd": r["cost"], "total_ms": r["ms"],
        "tokens_in": r["tin"], "tokens_out": r["tout"],
        "avg_cost_usd": (r["cost"] / n) if n else 0.0, "avg_ms": (r["ms"] / n) if n else 0,
    }
