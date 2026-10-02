"""花费安全阀:滚动 24 小时、全部书合计;超限即停,走现有的 gen_error + 退避路径。"""
import json

import pytest

from huaben import repo
from huaben.budget import BudgetExceeded, BudgetGuard, spent_recently
from huaben.config import Settings
from huaben.db import connect
from huaben.human_errors import explain
from huaben.llm_fake import FakeLLM
from huaben.scheduler import top_up

PLAN = json.dumps({"goal": "g", "beats": ["a"], "plant": [], "resolve": [], "target_chapters": 30})


@pytest.fixture
def db(tmp_path):
    s = Settings(openrouter_api_key="x", data_dir=tmp_path, chapter_words=1, buffer_chapters=1, _env_file=None)
    conn = connect(s.db_path)
    return s, conn


def test_window_counts_all_books_and_only_last_24h(db):
    _, conn = db
    a, b = repo.create_book(conn, "a"), repo.create_book(conn, "b")
    repo.log_run(conn, a, "write", cost_usd=0.5)
    repo.log_run(conn, b, "write", cost_usd=0.7)
    repo.log_run(conn, a, "write", cost_usd=9.0)
    conn.execute("UPDATE pipeline_runs SET created_at = datetime('now', '-25 hours') WHERE cost_usd = 9.0")
    conn.commit()
    assert spent_recently(conn) == pytest.approx(1.2)


def test_guard_blocks_at_limit_and_passes_below(db):
    s, conn = db
    bid = repo.create_book(conn, "x")
    inner = FakeLLM(["ok"])
    guard = BudgetGuard(inner, s.db_path, limit_usd=1.0)
    repo.log_run(conn, bid, "write", cost_usd=0.4)
    assert guard.chat([]).text == "ok"              # 0.4 < 1.0:放行
    repo.log_run(conn, bid, "write", cost_usd=0.6)
    with pytest.raises(BudgetExceeded) as ei:        # 1.0 ≥ 1.0:拦下,且没有调用到真正的模型
        guard.chat([])
    assert ei.value.kind == "budget" and len(inner.calls) == 1
    assert "HUABEN_SPEND_LIMIT_USD_24H" in explain(ei.value)


def test_zero_limit_means_unlimited(db):
    s, conn = db
    repo.log_run(conn, repo.create_book(conn, "x"), "write", cost_usd=999)
    assert BudgetGuard(FakeLLM(["ok"]), s.db_path, limit_usd=0).chat([]).text == "ok"


def test_over_budget_book_shows_human_error(db):
    s, conn = db
    bid = repo.create_book(conn, "x")
    repo.update_book(conn, bid, status="serializing")
    repo.log_run(conn, bid, "opening", cost_usd=3.0)
    res = top_up(conn, BudgetGuard(FakeLLM([PLAN]), s.db_path, 2.0), s, bid)
    assert res.generated == 0 and "花费已达上限" in repo.get_book(conn, bid)["gen_error"]


def test_real_client_is_wrapped_and_health_reports_spend(tmp_path):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from huaben.api.app import create_app
    from huaben.api.deps import ensure_llm
    s = Settings(openrouter_api_key="k", data_dir=tmp_path, worker_enabled=False, spend_limit_usd_24h=5,
                 _env_file=None)
    connect(s.db_path).close()
    assert isinstance(ensure_llm(SimpleNamespace(settings=s, llm=None)), BudgetGuard)
    body = TestClient(create_app(s)).get("/api/health").json()
    assert body["spend_24h"] == {"spent_usd": 0, "remind_usd": 2.0, "limit_usd": 5, "over_remind": False,
                                 "unpriced_calls": 0, "reliable": True}
