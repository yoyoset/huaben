"""给已经在写的卷补章数预算(T003 只对新规划的卷生效)。

做法照搬"给旧卷补征战结构"(volume.fill_arc):一个显式触发的接口、一次模型调用,不放在写章路径上。
编辑看"本卷节拍 + 已写各章摘要",回答已经走完了几个节拍、剩下每个节拍各给几章;
程序拼成完整的 beat_chapters 并把卷的总章数改成新的和,下一章起生效。
"""
from .. import repo
from ..beat_budget import normalize_budget
from ..config import Settings
from ..llm import LLM
from . import volume_prompts
from .errors import ChapterFailed
from .jsonout import ParseError, extract_json
from .volume import _ask


def merge_budget(done_beats, remaining, beat_count: int, volume_done: int) -> list[int] | None:
    """已走完的节拍数 + 剩下每个节拍的章数 → 完整的 beat_chapters;形状不对返回 None。
    已走完的节拍把已写的 volume_done 章平摊掉(它们只用来让 locate 跳过去,具体怎么摊不影响以后);
    一个节拍都没走完时,已写的章都算在第一个节拍头上。"""
    if isinstance(done_beats, bool) or not isinstance(done_beats, int) or not 0 <= done_beats < beat_count:
        return None
    rest = normalize_budget(remaining, beat_count - done_beats)
    if rest is None:
        return None
    if done_beats == 0:
        return [rest[0] + volume_done, *rest[1:]]
    base, extra = divmod(volume_done, done_beats)
    return [base + (1 if j < extra else 0) for j in range(done_beats)] + rest


def rebudget(conn, llm: LLM, settings: Settings, book_id: int) -> dict:
    """给进行中的卷补章数预算(旧书升级用;新卷规划时就带着)。失败抛 ChapterFailed/LLMError。"""
    volume = repo.active_volume(conn, book_id)
    if volume is None:
        raise ChapterFailed("这本书没有进行中的卷", step="volume")
    summaries = [f"第{c['idx']}章《{c['title']}》:{c['summary']}"
                 for c in repo.chapter_index(conn, book_id, volume["id"])]

    def parse(text: str) -> tuple[list[int], int]:
        d = extract_json(text)
        done_beats = d.get("done_beats")
        budget = merge_budget(done_beats, d.get("remaining"), len(volume["beats"]), len(summaries))
        if budget is None:
            raise ParseError("节拍预算形状不对")
        return budget, done_beats

    # temperature=0.2:这是对照摘要的判断题,不是规划题——0.7 时同一个卷两次判断差两个节拍(T009)
    budget, done_beats = _ask(conn, llm, book_id, "volume_budget",
                              volume_prompts.budget_messages(volume, summaries), parse, temperature=0.2)
    old_target = volume["target_chapters"]
    repo.set_volume_budget(conn, volume["id"], budget, sum(budget))
    repo.log_run(conn, book_id, "volume_budget",
                 note=f"已走完 {done_beats} 个节拍;预算 {budget};总章数 {old_target}→{sum(budget)}")
    return {"beat_chapters": budget, "target_chapters": sum(budget), "done_beats": done_beats}
