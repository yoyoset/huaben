"""一本书的运行统计:回答 v0 验收的"贵不贵、慢不慢、稳不稳"。

口径(写清楚,避免误读):
- 单章平均成本 = (章级步骤 + 卷级步骤[规划/封卷])总费用 ÷ 已定稿章数。被打回、失败的稿子也花了钱,一并摊进来;
  开书对话的费用单列,不摊(它是一次性的)。
- 单章平均耗时 = 章级步骤总耗时 ÷ 已定稿章数(读者等的就是这个;卷级步骤偶发,单列)。
- 重写率 = 定稿章里写了不止一稿的比例。
"""
from . import repo
from .canon_size import canon_size


def _per(total: float, n: int) -> float:
    return total / n if n else 0.0


def book_stats(conn, book_id: int, audio_ok=lambda row: row["has_audio"]) -> dict:
    """audio_ok:判断一章(chapter_index 的一行)是否真的有能播的音频(API 层按文件核对;默认只看数据库登记)。"""
    t = repo.run_totals(conn, book_id)
    n = repo.count_accepted(conn, book_id)
    att = repo.attempt_stats(conn, book_id)
    voiced = sum(1 for c in repo.chapter_index(conn, book_id) if audio_ok(c))
    return {
        "chapters": n,
        "avg_cost_usd": _per(t["chapter"]["cost_usd"] + t["volume"]["cost_usd"], n),
        "avg_seconds": _per(t["chapter"]["ms"], n) / 1000,
        "avg_tokens_out": _per(t["chapter"]["tokens_out"], n),
        "total_cost_usd": sum(v["cost_usd"] for v in t.values()),
        "cost_breakdown_usd": {k: v["cost_usd"] for k, v in t.items()},
        "avg_attempts": att["avg"],
        "rewrite_rate": _per(att["rewritten"], n),
        "voiced": voiced,
        "failures": repo.failure_counts(conn, book_id),
        "recent_failures": repo.recent_failures(conn, book_id),
        "unpriced_calls": repo.unpriced_calls(conn, book_id),  # > 0 时金额偏低、不可信
        "canon": canon_size((repo.get_bible(conn, book_id) or {}).get("canon")),
    }
