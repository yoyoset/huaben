"""预生成缓冲:让每本连载中的书始终比读者进度多备 N 章,听/读时不用等。

只做"补货"这一件事:`top_up` 对单本书循环 [保证有卷 → 生成一章],直到缓冲够数或失败。
失败不无限重试:记到 books.gen_error 让界面可见(绝不"后台失败但用户以为成功"),本轮就此停手,
文本补货之后顺带给缺音频的章配音(tts 可选);
由外层(API 后台循环)按自己的节奏下次再来。
并发:同一本书同一时刻只允许一个补货在跑(进程内锁;v0 单进程部署,多进程需换成库级租约)。
"""
import logging
import threading
from dataclasses import dataclass

from . import repo
from .config import Settings
from .human_errors import explain
from .logs import log_context
from .llm import LLM, LLMError
from .pipeline.chapter import generate_chapter
from .pipeline.errors import ChapterFailed
from .pipeline.volume import ensure_active_volume
from .tts.base import TTS
from .tts.service import fill_audio

log = logging.getLogger("huaben.scheduler")
_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(book_id: int) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(book_id, threading.Lock())


@dataclass
class TopUpResult:
    generated: int = 0
    skipped: bool = False   # 别的补货正在跑这本书
    error: str = ""         # 非空表示本轮因文本生成失败而停手
    audio_error: str = ""   # 配音失败(文本照常可读,只是暂时没有音频)


def top_up(conn, llm: LLM, settings: Settings, book_id: int, max_chapters: int | None = None,
           tts: TTS | None = None) -> TopUpResult:
    lock = _lock_for(book_id)
    if not lock.acquire(blocking=False):
        return TopUpResult(skipped=True)
    res = TopUpResult()
    try:
        with log_context(book=book_id):
            return _fill(conn, llm, settings, book_id, max_chapters, tts, res)
    finally:
        lock.release()


def _fill(conn, llm: LLM, settings: Settings, book_id: int, max_chapters: int | None, tts: TTS | None,
          res: TopUpResult) -> TopUpResult:
    while repo.buffered_ahead(conn, book_id) < settings.buffer_chapters:
        if max_chapters is not None and res.generated >= max_chapters:
            break
        try:
            ensure_active_volume(conn, llm, settings, book_id)
            generate_chapter(conn, llm, settings, book_id)
        except Exception as e:  # noqa: BLE001 —— 包括程序缺陷:都必须让用户看见,不能静默停更
            if not isinstance(e, (ChapterFailed, LLMError)):
                log.exception("生成时出现未预期的错误")
            # 技术细节进 pipeline_runs/日志;界面上的 gen_error 只放人话
            repo.log_run(conn, book_id, "error", ok=False, note=f"{type(e).__name__}: {e}"[:300])
            res.error = explain(e)
            break
        res.generated += 1
    if tts is not None:  # 文本失败时也给已有章补音频;配音失败不影响文本缓冲
        _, res.audio_error = fill_audio(conn, tts, settings, book_id)
    repo.update_book(conn, book_id, gen_error=res.error or res.audio_error)
    if res.generated or res.error or res.audio_error:
        log.info("top_up generated=%d error=%s audio_error=%s", res.generated, bool(res.error), bool(res.audio_error))
    return res


def top_up_all(conn, llm: LLM, settings: Settings, tts: TTS | None = None) -> dict[int, TopUpResult]:
    """给所有连载中的书补货(开书中的不动)。一本书失败不影响其它书。"""
    return {b["id"]: top_up(conn, llm, settings, b["id"], tts=tts)
            for b in repo.list_books(conn) if b["status"] == "serializing"}
