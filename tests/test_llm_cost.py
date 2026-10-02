"""被丢弃但已计费的调用也要记账(路线 28)。

实测曾出现:上游 3 次都返回"200 + 空正文"(思考吃光 max_tokens,token 照扣),共计费 $0.036,
pipeline_runs 记下的花费却是 $0——花费上限对这种"失控烧钱"的典型形态完全失明。
"""
import httpx
import pytest

from huaben import repo
from huaben.budget import spent_recently
from huaben.config import Settings
from huaben.db import connect
from huaben.llm import LLMError, OpenRouterClient
from huaben.pipeline.llm_step import call_step

EMPTY = {"choices": [{"message": {"content": ""}, "finish_reason": "length"}],
         "usage": {"prompt_tokens": 3000, "completion_tokens": 8000, "cost": 0.012}}
OK = {"choices": [{"message": {"content": "正文"}, "finish_reason": "stop"}],
      "usage": {"prompt_tokens": 3000, "completion_tokens": 2000, "cost": 0.004}}


def client(s, replies):
    it = iter(replies)
    return OpenRouterClient(s, transport=httpx.MockTransport(lambda req: httpx.Response(200, json=next(it))),
                            sleep=lambda _: None)


@pytest.fixture
def env(tmp_path):
    s = Settings(openrouter_api_key="k", data_dir=tmp_path, _env_file=None)
    conn = connect(s.db_path)
    return s, conn, repo.create_book(conn, "书")


def test_all_empty_attempts_are_recorded_as_spend(env):
    s, conn, bid = env
    with pytest.raises(LLMError) as ei:
        call_step(conn, client(s, [EMPTY] * 3), bid, 1, "write", [{"role": "user", "content": "写"}], json_mode=False)
    assert ei.value.cost_usd == pytest.approx(0.036) and ei.value.tokens_out == 24000
    assert spent_recently(conn) == pytest.approx(0.036)  # 花费上限看得见
    row = conn.execute("SELECT ok, tokens_out FROM pipeline_runs WHERE step='write'").fetchone()
    assert row["ok"] == 0 and row["tokens_out"] == 24000


def test_empty_then_success_adds_the_wasted_cost_to_the_result(env):
    s, conn, bid = env
    res = call_step(conn, client(s, [EMPTY, OK]), bid, 1, "write", [{"role": "user", "content": "写"}], json_mode=False)
    assert res.text == "正文" and res.cost_usd == pytest.approx(0.016) and res.tokens_out == 10000
    assert spent_recently(conn) == pytest.approx(0.016)


def test_plain_success_is_unchanged(env):
    s, conn, bid = env
    res = client(s, [OK]).chat([{"role": "user", "content": "写"}])
    assert (res.cost_usd, res.tokens_in, res.tokens_out) == (pytest.approx(0.004), 3000, 2000)
