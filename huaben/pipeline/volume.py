"""卷的生命周期:规划新卷、封卷、保证始终有一个进行中的卷。

卷是规划单位,也是记忆压缩边界:封卷把本卷压成摘要并刷新全书梗概,之后旧卷原文不再进 prompt。
"""
from .. import repo
from ..config import Settings
from ..context import load_context
from ..db import tx
from ..llm import LLM
from . import volume_prompts
from .errors import ChapterFailed
from .llm_step import call_step
from .parsing import ParseError, parse_seal, parse_volume_plan

DEFAULT_TARGET_CHAPTERS = 30


def _ask(conn, llm: LLM, book_id: int, step: str, messages, parse):
    """调用编辑 + 解析;解析失败重试一次(格式问题多为偶发),仍失败抛 ChapterFailed。"""
    last = ""
    for _ in range(2):
        res = call_step(conn, llm, book_id, None, step, messages, json_mode=True, temperature=0.7)
        try:
            return parse(res.text)
        except ParseError as e:
            last = str(e)
            repo.log_run(conn, book_id, step, ok=False, note=f"parse: {e}"[:300])
    raise ChapterFailed(f"{step} 两次输出都无法解析: {last}")


def plan_volume(conn, llm: LLM, settings: Settings, book_id: int) -> dict:
    """规划并启用下一卷(开书时规划第 1 卷也走这里)。"""
    ctx = load_context(conn, book_id, settings.recent_chapters_in_prompt)
    idx = len(repo.list_volumes(conn, book_id)) + 1
    plan = _ask(conn, llm, book_id, "volume_plan", volume_prompts.plan_messages(ctx, idx), parse_volume_plan)
    vid = repo.create_volume(
        conn, book_id, idx, goal=plan["goal"], beats=plan["beats"], plant=plan["plant"], resolve=plan["resolve"],
        status="active", target_chapters=plan["target_chapters"] or DEFAULT_TARGET_CHAPTERS)
    return repo.get_volume(conn, vid)


def seal_volume(conn, llm: LLM, settings: Settings, book_id: int, volume: dict) -> None:
    """封卷:卷摘要 + 刷新全书梗概 + 并入世界设定定本,在一个事务里写入。"""
    ctx = load_context(conn, book_id, settings.recent_chapters_in_prompt)
    chapters = repo.accepted_chapters(conn, book_id, volume["id"])
    need_canon = bool(ctx.facts or (ctx.bible or {}).get("canon"))
    sealed = _ask(conn, llm, book_id, "volume_seal", volume_prompts.seal_messages(ctx, volume, chapters),
                  lambda text: parse_seal(text, canon_required=need_canon))
    with tx(conn):  # 卷摘要 + 全书梗概 + 世界设定定本 同一事务
        repo.seal_volume(conn, volume["id"], sealed["volume_summary"], commit=False)
        repo.update_book(conn, book_id, synopsis=sealed["synopsis"], commit=False)
        if sealed["canon"]:
            repo.save_bible(conn, book_id, canon=sealed["canon"], commit=False)


def ensure_active_volume(conn, llm: LLM, settings: Settings, book_id: int) -> dict:
    """调度器在每次写章前调用:当前卷写满就封卷并规划下一卷;没有进行中的卷就规划一卷。"""
    vol = repo.active_volume(conn, book_id)
    if vol is not None and len(repo.accepted_chapters(conn, book_id, vol["id"])) >= vol["target_chapters"]:
        seal_volume(conn, llm, settings, book_id, vol)
        vol = None
    return vol if vol is not None else plan_volume(conn, llm, settings, book_id)
