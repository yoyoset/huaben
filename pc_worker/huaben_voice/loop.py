"""主循环:取一章 → 合成 → 交回;没任务就歇一会儿;出错记一行、退避后继续,不退出。

一次只取一章:合成一章要几十秒到几分钟,取多了期间读者翻到别处,优先级就过时了;每章做完再问服务器"下一章是谁",
顺带让服务器知道电脑还在线。
"""
import logging
import time
from typing import Callable

from .client import VoiceClient
from .engines import Engine

log = logging.getLogger("huaben_voice")


def run_once(client: VoiceClient, engine: Engine) -> int:
    """处理至多一章,返回处理了几章(0 = 暂时没任务)。合成或上传出错直接抛,由调用方决定退避。"""
    jobs = client.fetch_jobs(limit=1)
    if not jobs:
        return 0
    job = jobs[0]
    t0 = time.monotonic()
    # "开始配""配好""出错了""引擎就绪"这几个词是启动器(launcher/HuabenVoice.cs)判断状态的依据,改措辞要两边一起改
    log.info("开始配 书 %s 第 %s 章《%s》(%d 字)", job["book_id"], job["idx"], job["title"], len(job["text"]))
    mp3 = engine.synthesize(job["text"])
    client.upload(job["book_id"], job["idx"], mp3)
    log.info("书 %s 第 %s 章《%s》配好:%d 字 → %.1f MB,用时 %.0f 秒", job["book_id"], job["idx"], job["title"],
             len(job["text"]), len(mp3) / 1e6, time.monotonic() - t0)
    return 1


def run_forever(client: VoiceClient, engine: Engine, idle_s: float = 30.0, max_backoff_s: float = 600.0,
                sleep: Callable[[float], None] = time.sleep, should_stop: Callable[[], bool] = lambda: False) -> None:
    backoff = idle_s
    while not should_stop():
        try:
            done = run_once(client, engine)
            backoff = idle_s
            if not done:
                sleep(idle_s)  # 没任务:歇一会儿再问(这次询问本身就是心跳)
        except Exception as e:  # noqa: BLE001 —— 服务器重启、网络抖动、单章合成失败都不应让程序退出
            log.warning("出错了,%.0f 秒后重试:%s", backoff, e)
            sleep(backoff)
            backoff = min(backoff * 2, max_backoff_s)
