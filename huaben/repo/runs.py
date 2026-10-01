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
