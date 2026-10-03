"""单章流水线编排:编辑·章纲 → 作者·正文 → 编辑·入账与核对(冲突则打回重写)。

原则:任何一步失败都要显式失败(抛 ChapterFailed + pipeline_runs 留痕 + 日志),
绝不能让"后台没写出来、读者以为有"。入账只发生在核对通过之后,且是原子的。
"""
import logging

from .. import repo
from ..config import Settings
from ..context import StoryContext, load_context
from ..db import dumps
from ..llm import LLM
from ..logs import log_context
from . import prompts
from .chop import chop_problems
from .draft_check import clean_draft, copy_problems, draft_problems
from .restage import restage_problems
from .errors import ChapterFailed, NoActiveVolume
from .ledger_apply import apply_ledger
from .llm_step import call_step
from .parsing import ParseError, parse_ledger, parse_outline, unplanned_contradictions
from ..planting import to_register
from ..repetition import repetition_note
from ..script_import import resolve_keys
from ..verbatim import ending_problem, lines_feedback, missing_lines

log = logging.getLogger("huaben.chapter")


def _reject(conn, book_id: int, idx: int, note: str) -> None:
    """一次没通过的检查:进 pipeline_runs(统计/对账用)并打一行日志(排查用)。"""
    repo.log_run(conn, book_id, "check", chapter_idx=idx, ok=False, note=note[:300])
    log.warning("check=reject %s", note[:200])


def _fail(conn, book_id: int, chapter_id: int, idx: int, step: str, reason: str) -> ChapterFailed:
    repo.update_chapter(conn, chapter_id, status="failed")
    _reject(conn, book_id, idx, f"{step}: {reason}")
    log.error("chapter=failed step=%s reason=%s", step, reason)
    return ChapterFailed(f"chapter {idx} failed at {step}: {reason}", step=step, idx=idx)


def _record(conn, llm: LLM, book_id: int, idx: int, messages) -> dict | None:
    """编辑·入账。输出格式问题多为偶发,先只重试入账这一步(同一稿正文),两次都不行才返回 None。"""
    for _ in range(2):
        rec = call_step(conn, llm, book_id, idx, "ledger", messages, json_mode=True, temperature=0.2)
        try:
            return parse_ledger(rec.text)
        except ParseError as e:
            _reject(conn, book_id, idx, f"ledger parse: {e}")
    return None


def _thread_follow_through(ctx, outline: dict, ledger: dict) -> list[str]:
    """章纲点名要推进的伏笔,入账里却没有任何进展:不打回(可能只是没写到),但留痕供对账。"""
    open_ids = {f["id"] for f in ctx.foreshadows}
    touched = {u["id"] for u in ledger["foreshadows_update"]}
    notes = [f"章纲点名的伏笔 #{i} 本章未见推进" for i in outline["foreshadows"] if i in open_ids and i not in touched]
    notes += [f"章纲点名的伏笔 #{i} 不存在或已回收" for i in outline["foreshadows"] if i not in open_ids]
    return notes


def generate_chapter(conn, llm: LLM, settings: Settings, book_id: int) -> dict:
    """生成并定稿下一章,返回定稿后的章记录。失败抛 ChapterFailed。"""
    repo.discard_unaccepted(conn, book_id)
    ctx = load_context(conn, book_id, settings.recent_chapters_in_prompt)
    if ctx.volume is None:
        raise NoActiveVolume(f"book {book_id} has no active volume", step="volume")
    with log_context(chapter=ctx.next_idx):
        chapter_id, outline = _outline(conn, llm, book_id, ctx)
        return _draft_until_accepted(conn, llm, settings, book_id, ctx, chapter_id, outline)


def _outline(conn, llm: LLM, book_id: int, ctx: StoryContext) -> tuple[int, dict]:
    """编辑·章纲。剧本书的章纲来自导入的剧本,不调模型;非剧本书走原路(解析失败重试一次)。
    标题与已有章重复只留痕、不重出:提示里已列出已有标题做预防,撞名是质量问题、不是停更或多花一次调用的理由。"""
    idx = ctx.next_idx
    scripted = repo.get_scripted_outline(conn, book_id, idx)
    if scripted is not None:
        raw, missing = resolve_keys(scripted, repo.foreshadow_ids_by_key(conn, book_id))
        outline = parse_outline(dumps(raw))  # 代号翻译后过规整;节奏标记只留在 scripted_outlines,不进章纲
        if missing:
            repo.log_run(conn, book_id, "outline", chapter_idx=idx, note=f"剧本引用了不存在的伏笔代号: {missing}")
        chapter_id = repo.create_chapter(conn, book_id, ctx.volume["id"], idx,
                                         outline=dumps(outline), title=outline["title"])
        repo.log_run(conn, book_id, "outline", chapter_idx=idx, note="outline: 来自剧本")
        return chapter_id, outline
    if ctx.book.get("scripted"):
        raise ChapterFailed("这一批剧本已经写完,等下一批剧本导入后继续", step="script", idx=idx)
    outline, res = None, None
    for _ in range(2):
        res = call_step(conn, llm, book_id, idx, "outline", prompts.outline_messages(ctx), json_mode=True, temperature=0.7)
        try:
            outline = parse_outline(res.text)
            break
        except ParseError as e:
            repo.log_run(conn, book_id, "outline", chapter_idx=idx, ok=False, note=f"parse: {e}"[:300])
    if outline is not None and outline["title"] in set(ctx.titles):
        repo.log_run(conn, book_id, "outline", chapter_idx=idx, note=f"标题与已有章重复: {outline['title']}"[:300])
    chapter_id = repo.create_chapter(conn, book_id, ctx.volume["id"], idx,
                                     outline=res.text if outline is None else dumps(outline),
                                     title=outline["title"] if outline else "")
    if outline is None:
        raise _fail(conn, book_id, chapter_id, idx, "outline", "章纲两次都无法解析")
    return chapter_id, outline


def _imported_text(conn, llm: LLM, settings: Settings, book_id: int, ctx: StoryContext,
                   chapter_id: int, outline: dict) -> dict:
    """架构方写好的正文:不用作者模型,直接记账。机械检查与账本出入只留痕、不打回(没有"重写"这一步)。"""
    idx = ctx.next_idx
    body = clean_draft(repo.get_scripted_body(conn, book_id, idx))
    repo.update_chapter(conn, chapter_id, body=body, status="written")
    repo.log_run(conn, book_id, "write", chapter_idx=idx, note="write: 来自导入的正文")
    prev = ctx.recent[-1]["body"] if ctx.recent else ""
    for p in (draft_problems(body, settings.chapter_words) + copy_problems(body, [c["body"] for c in ctx.recent])
              + restage_problems(body, prev, [c["name"] for c in ctx.characters])
              + chop_problems(body)
              + lines_feedback(missing_lines(body, outline.get("lines") or []))
              + ending_problem(body, outline.get("ending") or "")):
        repo.log_run(conn, book_id, "write", chapter_idx=idx, note=f"导入正文的提醒(未打回):{p}")
    ledger = _record(conn, llm, book_id, idx, prompts.ledger_messages(ctx, outline, body))
    if ledger is None:
        raise _fail(conn, book_id, chapter_id, idx, "ledger", "导入正文的入账两次都无法解析")
    for bad in unplanned_contradictions(ledger):
        repo.log_run(conn, book_id, "ledger", chapter_idx=idx, note=f"导入正文与账本的出入(未打回):{bad}")
    ledger["foreshadows_new"], plant_notes = to_register(
        outline.get("plant"), len(ctx.foreshadows), ledger["foreshadows_new"],
        scripted=bool(ctx.book.get("scripted")))
    for w in apply_ledger(conn, book_id, chapter_id, idx, ledger) + _thread_follow_through(ctx, outline, ledger) + plant_notes:
        repo.log_run(conn, book_id, "ledger", chapter_idx=idx, note=w)
    note = repetition_note(body, [c["name"] for c in ctx.characters])  # 逐字重复:只留痕,不打回
    if note:
        repo.log_run(conn, book_id, "check", chapter_idx=idx, note=note)
    repo.log_run(conn, book_id, "check", chapter_idx=idx, note="accepted at attempt 1(导入)")
    return repo.get_chapter(conn, book_id, idx)


def _draft_until_accepted(conn, llm: LLM, settings: Settings, book_id: int, ctx: StoryContext,
                          chapter_id: int, outline: dict) -> dict:
    """作者·正文 → 机械底线 → 编辑·入账核对;不过则带反馈重写,最多 max_write_attempts 稿。"""
    idx, feedback = ctx.next_idx, []
    if repo.get_scripted_body(conn, book_id, idx) is not None:
        return _imported_text(conn, llm, settings, book_id, ctx, chapter_id, outline)
    for attempt in range(1, settings.max_write_attempts + 1):
        repo.update_chapter(conn, chapter_id, attempts=attempt)
        draft = call_step(conn, llm, book_id, idx, "write",
                          prompts.write_messages(ctx, outline, settings.chapter_words, feedback),
                          json_mode=False, max_tokens=settings.chapter_max_tokens)
        if draft.truncated:
            feedback = ["上一稿被截断,没有写完;请控制篇幅,完整写到结尾钩子。"]
            _reject(conn, book_id, idx, "truncated")
            continue
        body = clean_draft(draft.text)
        prev = ctx.recent[-1]["body"] if ctx.recent else ""
        problems = (draft_problems(body, settings.chapter_words) + copy_problems(body, [c["body"] for c in ctx.recent])
                    + restage_problems(body, prev, [c["name"] for c in ctx.characters])
                    + lines_feedback(missing_lines(body, outline.get("lines") or []))
                    + ending_problem(body, outline.get("ending") or "")
                    + chop_problems(body))
        if problems:  # 机械底线不过:不花入账的钱,直接带理由重写
            _reject(conn, book_id, idx, "draft: " + "; ".join(problems))
            feedback = problems
            continue
        repo.update_chapter(conn, chapter_id, body=body, status="written")
        ledger = _record(conn, llm, book_id, idx, prompts.ledger_messages(ctx, outline, body))
        if ledger is None:
            feedback = []  # 入账两次都解析失败:不是正文的错,不带反馈,再来一稿
            continue
        bad = unplanned_contradictions(ledger)
        if bad:
            _reject(conn, book_id, idx, "contradiction: " + "; ".join(bad))
            feedback = bad
            continue
        # 登记伏笔以章纲的 plant 为准;入账捡出来的只留痕,不登记(不知道答案的"神秘细节"不是伏笔)
        ledger["foreshadows_new"], plant_notes = to_register(
            outline.get("plant"), len(ctx.foreshadows), ledger["foreshadows_new"],
            scripted=bool(ctx.book.get("scripted")))
        for w in apply_ledger(conn, book_id, chapter_id, idx, ledger) + _thread_follow_through(ctx, outline, ledger) + plant_notes:
            repo.log_run(conn, book_id, "ledger", chapter_idx=idx, note=w)
        note = repetition_note(body, [c["name"] for c in ctx.characters])  # 逐字重复:只留痕,不打回(分不清复沓与词穷)
        if note:
            repo.log_run(conn, book_id, "check", chapter_idx=idx, note=note)
        repo.log_run(conn, book_id, "check", chapter_idx=idx, note=f"accepted at attempt {attempt}")
        log.info("chapter=accepted attempt=%d title=%s chars=%d", attempt, outline["title"], len(body))
        return repo.get_chapter(conn, book_id, idx)
    raise _fail(conn, book_id, chapter_id, idx, "write", f"{settings.max_write_attempts} 稿均未通过核对")
