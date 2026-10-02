"""电脑配音程序的任务队列:接下来该配哪几章。

只给连载中的书出任务;每本书内部按 listening_order(读者接下来要听的先配);
多本书之间**轮流**取——每本书最急的那一章先上,一本书大批积压(比如恢复备份后要全部重配)不会挡住
另一个人正在听的那一章。家里每人一个书架,这一点比单人时更要紧。
"""
from . import repo
from .config import Settings
from .tts.service import chapters_needing_audio, listening_order, stale_voice
from .tts.store import best_playable, index_paths


def interleave(per_book: list[list[dict]], limit: int) -> list[dict]:
    """轮流从每个队列取一个:第 1 轮取各本最急的,第 2 轮取各本第二急的……最多 limit 个。纯函数。"""
    out: list[dict] = []
    rank = 0
    while len(out) < limit and any(rank < len(q) for q in per_book):
        out += [q[rank] for q in per_book if rank < len(q)][: limit - len(out)]
        rank += 1
    return out


def pending_jobs(conn, settings: Settings, limit: int, voice: str = "") -> list[dict]:
    """还没有电脑版(hq)音频、或电脑版文件丢了的章(完整行,含正文);
    voice 非空(电脑报上自己的音色)时,再加上读者还没听到、但是别的音色配的章——排在缺音频的后面。"""
    per_book = []
    for b in repo.list_books(conn):
        if b["status"] != "serializing":
            continue
        pos = max(1, b["last_opened"])
        need = listening_order(chapters_needing_audio(conn, settings, b["id"], "hq"), pos)
        if voice:
            missing = {c["idx"] for c in need}
            voiced = [c for c in repo.voiced_chapters(conn, b["id"], "hq") if c["idx"] not in missing]
            need += stale_voice(voiced, voice, pos)
        per_book.append(need)
    return interleave(per_book, limit)


def unplayable_count(conn, settings: Settings, book_id: int) -> int:
    """现在一份能播的音频都没有的章数(界面提示"有 N 章在等配音"用)。"""
    return sum(1 for c in repo.chapter_index(conn, book_id) if best_playable(settings, index_paths(c)) is None)
