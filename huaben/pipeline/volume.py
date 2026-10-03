"""卷的生命周期:规划新卷、封卷、保证始终有一个进行中的卷。

卷是规划单位,也是记忆压缩边界:封卷把本卷压成摘要并刷新全书梗概,之后旧卷原文不再进 prompt。
"""
import logging

from .. import repo
from ..arc import normalize_arc, past_modes
from ..canon_size import CANON_WARN_CHARS, canon_size, seal_note
from ..config import Settings
from ..context import load_context
from ..db import tx
from ..llm import LLM
from . import volume_prompts
from .errors import ChapterFailed
from .llm_step import call_step
from .parsing import ParseError, extract_json, parse_seal, parse_volume_plan

DEFAULT_TARGET_CHAPTERS = 30
log = logging.getLogger("huaben.volume")


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
    raise ChapterFailed(f"{step} 两次输出都无法解析: {last}", step=step)


def plan_volume(conn, llm: LLM, settings: Settings, book_id: int) -> dict:
    """规划并启用下一卷(开书时规划第 1 卷也走这里)。"""
    ctx = load_context(conn, book_id, settings.recent_chapters_in_prompt)
    volumes = repo.list_volumes(conn, book_id)
    idx = len(volumes) + 1
    carried = unresolved_targets(conn, book_id, volumes[-1]) if volumes else []
    plan = _ask(conn, llm, book_id, "volume_plan",
                volume_prompts.plan_messages(ctx, idx, carried, past_modes(volumes)), parse_volume_plan)
    open_ids = {f["id"] for f in ctx.foreshadows}
    resolve = [i for i in plan["resolve"] if i in open_ids]
    if len(resolve) < len(plan["resolve"]):  # 编号不存在或早已回收:丢掉并留痕,不让卷计划指向不存在的伏笔
        dropped = [i for i in plan["resolve"] if i not in open_ids]
        repo.log_run(conn, book_id, "volume_plan", note=f"resolve 中无效的伏笔编号已忽略: {dropped}")
    vid = repo.create_volume(
        conn, book_id, idx, goal=plan["goal"], beats=plan["beats"], plant=plan["plant"], resolve=resolve,
        status="active", target_chapters=plan["target_chapters"] or DEFAULT_TARGET_CHAPTERS, arc=plan["arc"])
    return repo.get_volume(conn, vid)


def fill_arc(conn, llm: LLM, settings: Settings, book_id: int) -> dict:
    """给进行中的卷补征战结构:旧书一次性升级,或规划时模型没给全。显式调用(接口/运维),不放在写章路径上——
    写章前多一次模型调用,网络一抖就会拖住正文;而需要补的只是少数旧卷。失败抛 ChapterFailed/LLMError。"""
    volume = repo.active_volume(conn, book_id)
    if volume is None:
        raise ChapterFailed("这本书没有进行中的卷", step="volume")
    ctx = load_context(conn, book_id, settings.recent_chapters_in_prompt)
    summaries = [f"第{c['idx']}章《{c['title']}》:{c['summary']}" for c in repo.chapter_index(conn, book_id, volume["id"])]
    earlier = [v for v in repo.list_volumes(conn, book_id) if v["idx"] < volume["idx"]]
    arc = _ask(conn, llm, book_id, "volume_arc",
               volume_prompts.arc_messages(ctx, volume, summaries, past_modes(earlier)),
               lambda text: normalize_arc(extract_json(text), len(volume["beats"])) or _missing())
    repo.set_volume_arc(conn, volume["id"], arc)
    return arc


def _missing():
    raise ParseError("征战结构缺少对手/道理/赌注/谷底/代价/变化中的某项")


def unresolved_targets(conn, book_id: int, volume: dict) -> list[int]:
    """卷计划要收、但到现在还没收的伏笔编号。"""
    status = {f["id"]: f["status"] for f in repo.list_foreshadows(conn, book_id)}
    return [i for i in volume["resolve"] if isinstance(i, int) and status.get(i) not in (None, "resolved")]


def seal_volume(conn, llm: LLM, settings: Settings, book_id: int, volume: dict) -> None:
    """封卷:卷摘要 + 刷新全书梗概 + 并入世界设定定本,在一个事务里写入。"""
    ctx = load_context(conn, book_id, settings.recent_chapters_in_prompt)
    chapters = repo.chapter_index(conn, book_id, volume["id"])  # 封卷只需要章摘要
    need_canon = bool(ctx.facts or (ctx.bible or {}).get("canon"))
    sealed = _ask(conn, llm, book_id, "volume_seal", volume_prompts.seal_messages(ctx, volume, chapters),
                  lambda text: parse_seal(text, canon_required=need_canon))
    with tx(conn):  # 卷摘要 + 全书梗概 + 世界设定定本 同一事务
        repo.seal_volume(conn, volume["id"], sealed["volume_summary"], commit=False)
        repo.update_book(conn, book_id, synopsis=sealed["synopsis"], commit=False)
        if sealed["canon"]:
            repo.save_bible(conn, book_id, canon=sealed["canon"], commit=False)
    missed = unresolved_targets(conn, book_id, volume)
    old_canon = (ctx.bible or {}).get("canon") or ""
    new_canon = sealed["canon"] or old_canon
    if canon_size(new_canon)["too_long"]:
        log.warning("世界设定定本 %d 字,超过观测线 %d 字", len(new_canon.strip()), CANON_WARN_CHARS)
    # 对账:计划要收却没收的留痕(下一卷规划会点名优先安排);全收则记录"计划内伏笔全部回收"
    repo.log_run(conn, book_id, "volume_seal",
                 note=(f"第{volume['idx']}卷计划回收未完成: {missed}" if missed
                       else f"第{volume['idx']}卷计划内伏笔全部回收") + ";" + seal_note(old_canon, new_canon))


def ensure_active_volume(conn, llm: LLM, settings: Settings, book_id: int) -> dict:
    """调度器在每次写章前调用:当前卷写满就封卷并规划下一卷;没有进行中的卷就规划一卷。"""
    vol = repo.active_volume(conn, book_id)
    if vol is not None and repo.count_accepted(conn, book_id, vol["id"]) >= vol["target_chapters"]:
        seal_volume(conn, llm, settings, book_id, vol)
        vol = None
    return vol if vol is not None else plan_volume(conn, llm, settings, book_id)
