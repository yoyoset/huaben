"""电脑配音程序(PC 工人)的接口 + 界面上的配音状态。

拉取模式(docs/architecture.md 第 2 节):电脑主动来取任务、交音频,电脑不需要开端口,开机即干活、关机即停。
- GET  /api/voice/jobs            取接下来该配的几章(顺带记"电脑还在线")
- PUT  /api/voice/jobs/{book}/{idx} 交一章的 MP3(电脑版 hq;edge 版仍保留,播放优先电脑版)
- GET  /api/voice/status          界面用:模式、电脑在不在线、还有几章没有能播的音频
"""
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from .. import repo
from ..db import connect
from ..tts.mp3 import is_mp3
from ..tts.service import spoken_text
from ..tts.store import audio_relpath, remove_audio, write_audio
from ..voice_queue import pending_jobs, unplayable_count
from .background import voice_fallback_in_background
from .deps import book_or_404, get_conn

router = APIRouter(prefix="/api/voice", tags=["voice"])
MAX_AUDIO_BYTES = 200 * 1024 * 1024  # 一章十几分钟的 MP3 也就十几 MB;远超这个数说明传错了东西


def worker_auth(request: Request) -> None:
    token = request.app.state.settings.voice_worker_token
    if token and request.headers.get("authorization") != f"Bearer {token}":
        raise HTTPException(401, "配音程序的令牌不对(HUABEN_VOICE_WORKER_TOKEN)")


def _seen(request: Request) -> None:
    request.app.state.voice_seen = time.monotonic()


def worker_status(state) -> dict:
    seen = getattr(state, "voice_seen", None)
    ago = None if seen is None else time.monotonic() - seen
    return {"mode": state.settings.tts_mode, "worker_online": ago is not None and ago <= state.settings.voice_worker_online_s,
            "last_seen_s_ago": None if ago is None else round(ago)}


@router.get("/jobs", dependencies=[Depends(worker_auth)])
def jobs(request: Request, limit: int = Query(1, ge=1, le=10), voice: str = Query("", max_length=120),
         conn=Depends(get_conn)):
    """voice:电脑当前用的"引擎:音色"。带上它,读者还没听到的、别的音色配的章也会排进来重配。"""
    _seen(request)
    return [{"book_id": c["book_id"], "idx": c["idx"], "title": c["title"], "text": spoken_text(c)}
            for c in pending_jobs(conn, request.app.state.settings, limit, voice)]


def _save(settings, book_id: int, idx: int, data: bytes, voice: str = "") -> None:
    conn = connect(settings.db_path, check_same_thread=False)
    try:
        ch = repo.get_chapter(conn, book_id, idx)
        if ch is None or ch["status"] != "accepted":
            raise HTTPException(404, "没有这一章(或还没定稿)")
        old = repo.get_audio(conn, ch["id"], "hq")
        rel = audio_relpath(book_id, idx, "hq", voice)
        write_audio(settings, rel, data)
        repo.set_audio(conn, ch["id"], "hq", rel, voice=voice)
        if old and old["path"] != rel:  # 换了音色:新文件登记好之后再删旧的,中间任何时刻都有一份能播
            remove_audio(settings, old["path"])
        repo.log_run(conn, book_id, "tts", chapter_idx=idx, note=f"pc hq {len(data)} bytes {voice}".rstrip())
    finally:
        conn.close()


@router.put("/jobs/{book_id}/{idx}", dependencies=[Depends(worker_auth)])
async def upload(book_id: int, idx: int, request: Request, voice: str = Query("", max_length=120)):
    _seen(request)
    data = await request.body()
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413 if data else 400, "音频为空或过大")
    if not is_mp3(data):  # 播放器与锁屏续播都按 MP3 处理;别的格式在这里拦下,不入库
        raise HTTPException(415, "只接受 MP3")
    await run_in_threadpool(_save, request.app.state.settings, book_id, idx, data, voice)
    return {"ok": True}


@router.get("/status")
def status(request: Request, conn=Depends(get_conn)):
    settings = request.app.state.settings
    pending = sum(unplayable_count(conn, settings, b["id"]) for b in repo.list_books(conn) if b["status"] == "serializing")
    return {**worker_status(request.app.state), "pending": pending}


@router.post("/fallback/{book_id}", status_code=202)
def fallback(book_id: int, request: Request, tasks: BackgroundTasks, conn=Depends(get_conn)):
    """电脑没开、用户选"先用 edge-tts 配":在后台把这本书没音频的章用 edge 配上(电脑版之后照样会来升级)。"""
    book_or_404(conn, book_id)
    if request.app.state.tts is None:
        raise HTTPException(503, "服务器上没有可用的 edge-tts")
    tasks.add_task(voice_fallback_in_background, request.app.state, book_id)
    return {"started": True}
