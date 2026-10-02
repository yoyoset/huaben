"""上游不报费用时,花费上限与统计会静默失效 —— 必须看得见(路线 20)。"""
import logging

from fastapi.testclient import TestClient

from huaben import repo
from huaben.api.app import create_app
from huaben.budget import BudgetGuard
from huaben.config import Settings
from huaben.db import connect
from huaben.llm import LLMResult
from huaben.llm_fake import FakeLLM
from huaben.stats import book_stats


def settings(tmp_path):
    return Settings(openrouter_api_key="k", data_dir=tmp_path, worker_enabled=False, _env_file=None)


def test_counts_only_calls_with_tokens_but_no_cost(tmp_path):
    conn = connect(settings(tmp_path).db_path)
    a, b = repo.create_book(conn, "a"), repo.create_book(conn, "b")
    repo.log_run(conn, a, "write", tokens_in=100, tokens_out=200, cost_usd=0.0)   # 没报费用
    repo.log_run(conn, a, "write", tokens_in=100, tokens_out=200, cost_usd=0.002)  # 正常
    repo.log_run(conn, a, "tts", note="123 bytes")                                  # 不是模型调用
    repo.log_run(conn, b, "outline", tokens_in=50, tokens_out=0, cost_usd=0.0)
    repo.log_run(conn, b, "write", tokens_in=1, tokens_out=1, cost_usd=0.0)
    conn.execute("UPDATE pipeline_runs SET created_at = datetime('now', '-25 hours') WHERE tokens_in = 1")
    conn.commit()
    assert repo.unpriced_calls(conn) == 3
    assert repo.unpriced_calls(conn, a) == 1
    assert repo.unpriced_calls(conn, hours=24) == 2  # 25 小时前那条不在窗口里


def test_guard_warns_once_when_upstream_reports_no_cost(tmp_path, caplog):
    s = settings(tmp_path)
    connect(s.db_path).close()
    free = LLMResult(text="ok", tokens_in=100, tokens_out=200, cost_usd=0.0)
    guard = BudgetGuard(FakeLLM([free, free, "priced"]), s.db_path, limit_usd=1.0)
    with caplog.at_level(logging.WARNING, logger="huaben.budget"):
        for _ in range(3):
            guard.chat([{"role": "user", "content": "x"}])
    assert sum("没有返回本次调用的费用" in r.getMessage() for r in caplog.records) == 1  # 不刷屏


def test_health_and_stats_expose_unreliable_spend(tmp_path):
    s = settings(tmp_path)
    conn = connect(s.db_path)
    bid = repo.create_book(conn, "书")
    c = TestClient(create_app(s))
    assert c.get("/api/health").json()["spend_24h"]["reliable"] is True
    repo.log_run(conn, bid, "write", tokens_in=100, tokens_out=200, cost_usd=0.0)
    spend = c.get("/api/health").json()["spend_24h"]
    assert spend["reliable"] is False and spend["unpriced_calls"] == 1
    assert book_stats(conn, bid)["unpriced_calls"] == 1


def test_default_only_reminds_never_blocks(tmp_path):
    """2026-10-02 用户定:花费"提醒就好,不要限制那么死"——默认超过提醒线也照常调用模型。"""
    s = settings(tmp_path)
    assert s.spend_limit_usd_24h == 0 and s.spend_remind_usd_24h == 2.0
    conn = connect(s.db_path)
    bid = repo.create_book(conn, "书")
    repo.log_run(conn, bid, "write", tokens_in=1, tokens_out=1, cost_usd=2.5)
    guard = BudgetGuard(FakeLLM(["照常写"]), s.db_path, s.spend_limit_usd_24h)
    assert guard.chat([{"role": "user", "content": "x"}]).text == "照常写"
    body = TestClient(create_app(s)).get("/api/spend").json()
    assert body["over_remind"] is True and body["spent_usd"] == 2.5
