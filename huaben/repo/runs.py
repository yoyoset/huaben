"""可观测:每步耗时/token/费用。"""


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


def run_totals(conn, book_id: int) -> dict:
    """按"章级 / 卷级 / 开书"三类汇总费用、耗时、token。卷级与开书步骤没有章序号(chapter_idx 为空)。"""
    rows = conn.execute(
        "SELECT CASE WHEN chapter_idx IS NOT NULL THEN 'chapter' "
        "            WHEN step IN ('opening','finalize') THEN 'opening' ELSE 'volume' END AS kind, "
        "COALESCE(SUM(cost_usd),0) AS cost, COALESCE(SUM(duration_ms),0) AS ms, "
        "COALESCE(SUM(tokens_in),0) AS tin, COALESCE(SUM(tokens_out),0) AS tout "
        "FROM pipeline_runs WHERE book_id=? GROUP BY kind", (book_id,)).fetchall()
    empty = {"cost_usd": 0.0, "ms": 0, "tokens_in": 0, "tokens_out": 0}
    out = {k: dict(empty) for k in ("chapter", "volume", "opening")}
    for r in rows:
        out[r["kind"]] = {"cost_usd": r["cost"], "ms": r["ms"], "tokens_in": r["tin"], "tokens_out": r["tout"]}
    return out


def failure_counts(conn, book_id: int) -> dict[str, int]:
    return {r["step"]: r["n"] for r in conn.execute(
        "SELECT step, COUNT(*) AS n FROM pipeline_runs WHERE book_id=? AND ok=0 GROUP BY step ORDER BY n DESC",
        (book_id,))}


def recent_failures(conn, book_id: int, limit: int = 5) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT step, chapter_idx, note, created_at FROM pipeline_runs WHERE book_id=? AND ok=0 "
        "ORDER BY id DESC LIMIT ?", (book_id, limit))]


def editor_notes(conn, book_id: int, limit: int = 20) -> list[dict]:
    """编辑的软观察(拿不准的疑点/建议/逐字重复;不打回定稿)。写库时前缀固定,见 ledger_apply。"""
    return [dict(r) for r in conn.execute(
        "SELECT chapter_idx, note, created_at FROM pipeline_runs WHERE book_id=? AND step='ledger' "
        "AND note LIKE '编辑观察(未打回):%' ORDER BY id DESC LIMIT ?", (book_id, limit))]


def unpriced_calls(conn, book_id: int | None = None, hours: int | None = None) -> int:
    """用了 token 却没有记到费用的模型调用次数。

    费用取自上游返回的 usage.cost;换成不返回费用的兼容接口时它恒为 0——花费上限与统计会**静默失效**。
    从已记录的数据推导(不靠进程内状态),重启后照样看得见。免费模型也会被算进来,那时上限本来就无意义。
    """
    where, args = ["tokens_in + tokens_out > 0", "cost_usd = 0"], []
    if book_id is not None:
        where.append("book_id = ?")
        args.append(book_id)
    if hours is not None:
        where.append("created_at >= datetime('now', ?)")
        args.append(f"-{hours} hours")
    return conn.execute(f"SELECT COUNT(*) FROM pipeline_runs WHERE {' AND '.join(where)}", args).fetchone()[0]


def spent_usd(conn, hours: int) -> float:
    """过去 hours 小时、全部书合计的模型花费。"""
    return conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM pipeline_runs WHERE created_at >= datetime('now', ?)",
        (f"-{hours} hours",)).fetchone()[0]
