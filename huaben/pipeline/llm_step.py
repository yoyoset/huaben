"""一次 LLM 调用 + 记 pipeline_runs(耗时/token/费用)。失败也记,然后原样抛出。"""
import time

from .. import repo
from ..llm import LLM, LLMError, LLMResult


def call_step(conn, llm: LLM, book_id: int, idx: int | None, step: str, messages, *,
              json_mode: bool, max_tokens=None, temperature: float = 0.9) -> LLMResult:
    t0 = time.monotonic()
    try:
        res = llm.chat(messages, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode)
    except LLMError as e:
        repo.log_run(conn, book_id, step, chapter_idx=idx, ok=False, note=str(e)[:300],
                     duration_ms=int((time.monotonic() - t0) * 1000))
        raise
    repo.log_run(conn, book_id, step, chapter_idx=idx, duration_ms=res.duration_ms or int((time.monotonic() - t0) * 1000),
                 tokens_in=res.tokens_in, tokens_out=res.tokens_out, cost_usd=res.cost_usd)
    return res
