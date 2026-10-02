"""分层记忆·取数:把库里的状态装成"本章工作台"(StoryContext)。渲染见 render.py。

分两步,方便独立测试:
- load_context(conn, ...)  读库,产出 StoryContext(唯一碰数据库的地方)
- select_ledger  纯函数,只吃 dict/dataclass

分层(docs/architecture.md 3.3):全书梗概 → 往卷摘要 → 本卷章摘要 → 最近原文 → 账本(按章纲挑)。
封卷后旧卷原文不再进 prompt,所以第 500 章和第 50 章的 prompt 体量相当。
"""
from dataclasses import dataclass

from . import repo


@dataclass
class StoryContext:
    book: dict
    bible: dict
    volume: dict | None
    past_volume_summaries: list[tuple[int, str]]      # (卷序号, 摘要)
    volume_chapter_summaries: list[tuple[int, str, str]]  # (章序号, 标题, 摘要),不含 recent
    recent: list[dict]                                # 最近几章完整原文
    characters: list[dict]
    foreshadows: list[dict]                           # 未回收
    facts: list[dict]                                 # 本卷新确立的事实(往卷的已并入圣经 canon)
    next_idx: int = 1
    volume_done: int = 0                              # 本卷已定稿章数(卷进度 = volume_done+1 / target)


def load_context(conn, book_id: int, recent_n: int = 3) -> StoryContext:
    book = repo.get_book(conn, book_id)
    if book is None:
        raise KeyError(f"book {book_id} not found")
    volume = repo.active_volume(conn, book_id)
    recent = repo.recent_chapters(conn, book_id, recent_n)
    recent_idx = {c["idx"] for c in recent}
    vol_chapters = repo.accepted_chapters(conn, book_id, volume["id"]) if volume else []
    return StoryContext(
        book=book,
        bible=repo.get_bible(conn, book_id),
        volume=volume,
        past_volume_summaries=[(v["idx"], v["summary"]) for v in repo.list_volumes(conn, book_id)
                               if v["status"] == "sealed" and v["summary"]],
        volume_chapter_summaries=[(c["idx"], c["title"], c["summary"]) for c in vol_chapters
                                  if c["idx"] not in recent_idx and c["summary"]],
        recent=recent,
        characters=repo.list_characters(conn, book_id),
        foreshadows=repo.list_foreshadows(conn, book_id, open_only=True),
        facts=_volume_facts(conn, book_id),
        next_idx=repo.next_chapter_idx(conn, book_id),
        volume_done=len(vol_chapters),
    )


def _volume_facts(conn, book_id: int) -> list[dict]:
    """尚未封卷部分确立的事实。已封卷的在封卷时并入了圣经的世界设定定本(canon),不再逐条带。"""
    sealed_upto = conn.execute(
        "SELECT COALESCE(MAX(c.idx), 0) FROM chapters c JOIN volumes v ON v.id = c.volume_id "
        "WHERE v.book_id=? AND v.status='sealed' AND c.status='accepted'", (book_id,)).fetchone()[0]
    return [f for f in repo.list_facts(conn, book_id) if f["established_ch"] > sealed_upto]


def select_ledger(characters: list[dict], facts: list[dict], scope: str = "") -> tuple[list[dict], list[dict]]:
    """按检索文本挑账本。核心人物永远带(前身教训:名字没出现就不进上下文会导致名字漂移);
    非核心人物只有名字出现在 scope(章纲,核对时再加上正文)里才带;已死亡的人物也保留,否则会"复活"。
    """
    chars = [c for c in characters if c["core"] or (scope and c["name"] in scope)]
    return chars, facts
