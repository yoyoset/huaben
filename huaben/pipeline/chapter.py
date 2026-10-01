"""单章流水线编排:编辑·章纲 → 作者·正文 → 编辑·入账与核对(冲突则打回重写)。

原则:任何一步失败都要显式失败(抛 ChapterFailed + pipeline_runs 留痕),
绝不能让"后台没写出来、读者以为有"。入账只发生在核对通过之后,且是原子的。
"""
import time

from .. import repo
from ..config import Settings
from ..context import load_context
from ..db import dumps
from ..llm import LLM, LLMError, LLMResult
from . import prompts
from .ledger_apply import apply_ledger
from .parsing import ParseError, parse_ledger, parse_outline, unplanned_contradictions


class ChapterFailed(Exception):
    pass


class NoActiveVolume(ChapterFailed):
    """没有进行中的卷:需要先做卷规划(切片 5)。"""


def _call(conn, llm: LLM, book_id: int, idx: int, step: str, messages, *, json_mode: bool, max_tokens=None,
          temperature: float = 0.9) -> LLMResult:
    """一次 LLM 调用 + 记 pipeline_runs。失败也记,然后原样抛出。"""
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


def _fail(conn, book_id: int, chapter_id: int, idx: int, step: str, reason: str) -> ChapterFailed:
    repo.update_chapter(conn, chapter_id, status="failed")
    repo.log_run(conn, book_id, "check", chapter_idx=idx, ok=False, note=f"{step}: {reason}"[:300])
    return ChapterFailed(f"chapter {idx} failed at {step}: {reason}")


def generate_chapter(conn, llm: LLM, settings: Settings, book_id: int) -> dict:
    """生成并定稿下一章,返回定稿后的章记录。失败抛 ChapterFailed。"""
    repo.discard_unaccepted(conn, book_id)
    ctx = load_context(conn, book_id, settings.recent_chapters_in_prompt)
    if ctx.volume is None:
        raise NoActiveVolume(f"book {book_id} has no active volume")
    idx = ctx.next_idx

    # 1. 章纲(解析失败直接重试一次:格式问题多为偶发)
    outline = None
    for attempt in range(2):
        res = _call(conn, llm, book_id, idx, "outline", prompts.outline_messages(ctx), json_mode=True, temperature=0.7)
        try:
            outline = parse_outline(res.text)
            break
        except ParseError as e:
            repo.log_run(conn, book_id, "outline", chapter_idx=idx, ok=False, note=f"parse: {e}"[:300])
    chapter_id = repo.create_chapter(conn, book_id, ctx.volume["id"], idx,
                                     outline=res.text if outline is None else dumps(outline),
                                     title=outline["title"] if outline else "")
    if outline is None:
        raise _fail(conn, book_id, chapter_id, idx, "outline", "章纲两次都无法解析")

    # 2+3. 正文 → 入账核对;冲突/截断/解析失败则带反馈重写
    feedback: list[str] = []
    for attempt in range(1, settings.max_write_attempts + 1):
        repo.update_chapter(conn, chapter_id, attempts=attempt)
        draft = _call(conn, llm, book_id, idx, "write",
                      prompts.write_messages(ctx, outline, settings.chapter_words, feedback),
                      json_mode=False, max_tokens=settings.chapter_max_tokens)
        if draft.truncated:
            feedback = ["上一稿被截断,没有写完;请控制篇幅,完整写到结尾钩子。"]
            repo.log_run(conn, book_id, "check", chapter_idx=idx, ok=False, note="truncated")
            continue
        repo.update_chapter(conn, chapter_id, body=draft.text.strip(), status="written")
        rec = _call(conn, llm, book_id, idx, "ledger", prompts.ledger_messages(ctx, outline, draft.text),
                    json_mode=True, temperature=0.2)
        try:
            ledger = parse_ledger(rec.text)
        except ParseError as e:
            repo.log_run(conn, book_id, "check", chapter_idx=idx, ok=False, note=f"ledger parse: {e}"[:300])
            feedback = []  # 解析失败不是正文的错,不带反馈,直接再来一稿
            continue
        bad = unplanned_contradictions(ledger)
        if bad:
            repo.log_run(conn, book_id, "check", chapter_idx=idx, ok=False, note="contradiction: " + "; ".join(bad)[:250])
            feedback = bad
            continue
        for w in apply_ledger(conn, book_id, chapter_id, idx, ledger):
            repo.log_run(conn, book_id, "ledger", chapter_idx=idx, note=w)
        repo.log_run(conn, book_id, "check", chapter_idx=idx, note=f"accepted at attempt {attempt}")
        return repo.get_chapter(conn, book_id, idx)
    raise _fail(conn, book_id, chapter_id, idx, "write", f"{settings.max_write_attempts} 稿均未通过核对")

