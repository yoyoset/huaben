"""一次 LLM 调用 + 记 pipeline_runs(耗时/token/费用)+ 一行日志。失败也记,然后原样抛出。"""
import logging
import time

from .. import repo
from ..llm import LLM, LLMError, LLMResult

log = logging.getLogger("huaben.llm")


def call_step(conn, llm: LLM, book_id: int, idx: int | None, step: str, messages, *,
              json_mode: bool, max_tokens=None, temperature: float = 0.9) -> LLMResult:
    t0 = time.monotonic()
    try:
        res = llm.chat(messages, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode)
    except LLMError as e:
        ms = int((time.monotonic() - t0) * 1000)
        # 失败也可能已计费(空正文照扣 token):照实记,花费上限与统计才看得见
        repo.log_run(conn, book_id, step, chapter_idx=idx, ok=False, note=str(e)[:300], duration_ms=ms,
                     tokens_in=e.tokens_in, tokens_out=e.tokens_out, cost_usd=e.cost_usd)
        log.warning("step=%s ok=false kind=%s ms=%d err=%s", step, e.kind, ms, str(e)[:200])
        raise
    ms = res.duration_ms or int((time.monotonic() - t0) * 1000)
    repo.log_run(conn, book_id, step, chapter_idx=idx, duration_ms=ms,
                 tokens_in=res.tokens_in, tokens_out=res.tokens_out, cost_usd=res.cost_usd)
    log.info("step=%s ok=true ms=%d tokens_in=%d tokens_out=%d cost=%.5f%s", step, ms, res.tokens_in,
             res.tokens_out, res.cost_usd, " truncated=true" if res.truncated else "")
    return res
