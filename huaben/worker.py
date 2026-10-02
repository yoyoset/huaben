"""后台常驻补货:服务启动即巡检所有连载中的书(重启恢复),之后按间隔重复。

和 API 里"开书/翻页触发的补货"互补:触发式保证响应快,常驻式保证重启/漏触发后也能补齐。
失败退避:某本书补货失败后按指数退避(密钥失效、模型宕机时不会每分钟白打一次),成功即复位。
"""
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable

from . import repo
from .api.deps import ensure_llm
from .db import connect
from .human_errors import explain
from .llm import LLMError
from .scheduler import TopUpResult, top_up

log = logging.getLogger("huaben.worker")


class Backoff:
    """按 key(书 id)记录连续失败次数,算出"多久之后才允许再试"。时钟可注入便于测试。"""

    def __init__(self, base_s: float, cap_s: float, clock: Callable[[], float] = time.monotonic):
        self._base, self._cap, self._clock = base_s, cap_s, clock
        self._fails: dict[int, int] = {}
        self._next_ok: dict[int, float] = {}

    def fresh(self) -> "Backoff":
        """同样参数的一份独立退避(文字与配音各用一份,互不拖累)。"""
        return Backoff(self._base, self._cap, self._clock)

    def ready(self, key: int) -> bool:
        return self._clock() >= self._next_ok.get(key, 0.0)

    def record(self, key: int, ok: bool) -> None:
        if ok:
            self._fails.pop(key, None)
            self._next_ok.pop(key, None)
            return
        n = self._fails.get(key, 0) + 1
        self._fails[key] = n
        self._next_ok[key] = self._clock() + min(self._base * 2 ** (n - 1), self._cap)


class Worker:
    def __init__(self, state, interval_s: float, backoff: Backoff):
        self._state, self._interval, self._backoff = state, interval_s, backoff
        # 配音单独退避:配音服务挂了不能让文字缓冲跟着停(读者可以先读)
        self._audio_backoff = backoff.fresh()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_tick_at: str | None = None  # 供 /api/health 判断后台是否还在转
        self.ticks = 0
        self._llm_missing = False  # 没配密钥只在状态变化时记一次日志,不每分钟刷屏

    def tick(self) -> dict[int, TopUpResult]:
        """巡检一遍。任何异常都只记日志,绝不让后台线程死掉。"""
        results: dict[int, TopUpResult] = {}
        try:
            llm = ensure_llm(self._state)
        except LLMError as e:
            if not self._llm_missing:
                log.warning("后台补货暂停:%s(配置好后会自动恢复)", e)
            self._llm_missing = True
            self._show_blocked(explain(e))
            return results
        if self._llm_missing:
            log.info("LLM 已可用,后台补货恢复")
            self._llm_missing = False
        conn = connect(self._state.settings.db_path, check_same_thread=False)
        try:
            for b in repo.list_books(conn):
                if b["status"] != "serializing":
                    continue
                res = self._tick_book(conn, llm, b["id"])
                if res is not None:
                    results[b["id"]] = res
        except Exception:  # noqa: BLE001
            log.exception("后台巡检异常")
        finally:
            conn.close()
        return results

    def _show_blocked(self, reason: str) -> None:
        """没有可用的模型时,把原因写到**正在等文字**的书上(缓冲不满的连载书)。
        此前只记一行日志,书页一直显示"还在写"直到轮询放弃,读者不知道是卡在了配置上。
        缓冲已满的书暂时不受影响,不打扰;模型恢复后第一次补货会用结果覆盖(成功即清空)。"""
        conn = connect(self._state.settings.db_path, check_same_thread=False)
        try:
            for b in repo.list_books(conn):
                if (b["status"] == "serializing" and b["gen_error"] != reason
                        and repo.buffered_ahead(conn, b["id"]) < self._state.settings.buffer_chapters):
                    repo.update_book(conn, b["id"], gen_error=reason)
        except Exception:  # noqa: BLE001 —— 写提示失败不能让后台线程死掉
            log.exception("写入'模型不可用'提示失败")
        finally:
            conn.close()

    def _tick_book(self, conn, llm, book_id: int) -> TopUpResult | None:
        text_ok = self._backoff.ready(book_id)
        tts = self._state.tts if self._state.tts and self._audio_backoff.ready(book_id) else None
        if not text_ok and tts is None:
            return None  # 两类都在退避中
        try:
            res = top_up(conn, llm, self._state.settings, book_id, tts=tts, text=text_ok)
        except Exception:  # noqa: BLE001 —— 单本书的意外不能影响其它书和线程存活
            log.exception("书 %s 补货异常", book_id)
            self._backoff.record(book_id, ok=False)
            return None
        if not res.skipped:
            if text_ok:
                self._backoff.record(book_id, ok=not res.error)
            if tts is not None:
                self._audio_backoff.record(book_id, ok=not res.audio_error)
        return res

    def _run(self) -> None:
        while not self._stop.is_set():  # 先巡检再等待:启动即恢复
            self.tick()
            self.ticks += 1
            self.last_tick_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self._stop.wait(self._interval)

    def status(self) -> dict:
        alive = bool(self._thread and self._thread.is_alive())
        return {"enabled": True, "running": alive, "ticks": self.ticks, "last_tick_at": self.last_tick_at,
                "interval_s": self._interval}

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="huaben-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
