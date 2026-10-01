"""预生成缓冲:让每本连载中的书始终比读者进度多备 N 章,听/读时不用等。

只做"补货"这一件事:`top_up` 对单本书循环 [保证有卷 → 生成一章],直到缓冲够数或失败。
失败不无限重试:记到 books.gen_error 让界面可见(绝不"后台失败但用户以为成功"),本轮就此停手,
由外层(API 后台循环)按自己的节奏下次再来。
并发:同一本书同一时刻只允许一个补货在跑(进程内锁;v0 单进程部署,多进程需换成库级租约)。
"""
import threading
from dataclasses import dataclass

from . import repo
from .config import Settings
from .llm import LLM, LLMError
from .pipeline.chapter import generate_chapter
from .pipeline.errors import ChapterFailed
from .pipeline.volume import ensure_active_volume

_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(book_id: int) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(book_id, threading.Lock())


@dataclass
class TopUpResult:
    generated: int = 0
    skipped: bool = False   # 别的补货正在跑这本书
    error: str = ""         # 非空表示本轮因失败而停手


def top_up(conn, llm: LLM, settings: Settings, book_id: int, max_chapters: int | None = None) -> TopUpResult:
    lock = _lock_for(book_id)
    if not lock.acquire(blocking=False):
        return TopUpResult(skipped=True)
    res = TopUpResult()
    try:
        while repo.buffered_ahead(conn, book_id) < settings.buffer_chapters:
            if max_chapters is not None and res.generated >= max_chapters:
                break
            try:
                ensure_active_volume(conn, llm, settings, book_id)
                generate_chapter(conn, llm, settings, book_id)
            except (ChapterFailed, LLMError) as e:
                res.error = f"{type(e).__name__}: {e}"[:300]
                repo.update_book(conn, book_id, gen_error=res.error)
                return res
            res.generated += 1
        repo.update_book(conn, book_id, gen_error="")
        return res
    finally:
        lock.release()


def top_up_all(conn, llm: LLM, settings: Settings) -> dict[int, TopUpResult]:
    """给所有连载中的书补货(开书中的不动)。一本书失败不影响其它书。"""
    return {b["id"]: top_up(conn, llm, settings, b["id"])
            for b in repo.list_books(conn) if b["status"] == "serializing"}
