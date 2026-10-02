"""阅读与收听:章节列表 / 正文 / 音频流 / 读到哪。只暴露已定稿的章,章纲等内部工单不外露。"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import repo
from ..tts.service import chapter_audio
from ..tts.store import best_playable, index_paths
from .background import topup_in_background
from .deps import book_or_404, get_conn

router = APIRouter(prefix="/api/books/{book_id}", tags=["reading"])


class Progress(BaseModel):
    chapter: int = Field(ge=1)  # 刚打开/开始播放的章


def _accepted(conn, book_id: int, idx: int) -> dict:
    ch = repo.get_chapter(conn, book_id, idx)
    if ch is None or ch["status"] != "accepted":
        raise HTTPException(404, "这一章还没写好")
    return ch


@router.get("/chapters")
def chapters(book_id: int, request: Request, conn=Depends(get_conn)):
    book_or_404(conn, book_id)
    settings = request.app.state.settings
    return [{"idx": c["idx"], "title": c["title"], "has_audio": best_playable(settings, index_paths(c)) is not None}
            for c in repo.chapter_index(conn, book_id)]


@router.get("/chapters/{idx}")
def chapter(book_id: int, idx: int, request: Request, conn=Depends(get_conn)):
    book_or_404(conn, book_id)
    ch = _accepted(conn, book_id, idx)
    rel = chapter_audio(conn, request.app.state.settings, ch["id"])
    # 地址里带上是哪一份:电脑版替换 edge 版后地址随之变化,浏览器不会继续播缓存里的旧音频
    return {"idx": idx, "title": ch["title"], "body": ch["body"],
            "audio_url": f"/api/books/{book_id}/chapters/{idx}/audio?v={rel.replace('/', '_')}" if rel else None}


@router.get("/chapters/{idx}/audio")
def audio(book_id: int, idx: int, request: Request, conn=Depends(get_conn)):
    book_or_404(conn, book_id)
    settings = request.app.state.settings
    rel = chapter_audio(conn, settings, _accepted(conn, book_id, idx)["id"])
    if rel is None:
        raise HTTPException(404, "这一章的音频还没准备好")
    path = settings.audio_dir / rel
    # FileResponse 自带 Range 支持:iOS 的 <audio> 必须能分段取流才能拖动/锁屏续播
    return FileResponse(path, media_type="audio/mpeg")


@router.put("/progress")
def progress(book_id: int, body: Progress, request: Request, tasks: BackgroundTasks, conn=Depends(get_conn)):
    """记录读者打开/播放了哪一章。续读位置随之变化;最远进度只增不减(翻回去重读不影响预生成)。"""
    book = book_or_404(conn, book_id)
    _accepted(conn, book_id, body.chapter)  # 只能是已写好的章
    advanced = repo.open_chapter(conn, book_id, body.chapter)
    if advanced and book["status"] == "serializing":  # 读到了新的地方 → 缓冲变薄 → 后台补货
        tasks.add_task(topup_in_background, request.app.state, book_id)
    b = repo.get_book(conn, book_id)
    return {"read_pos": b["read_pos"], "last_opened": b["last_opened"]}
