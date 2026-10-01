"""阅读与收听:章节列表 / 正文 / 音频流 / 读到哪。只暴露已定稿的章,章纲等内部工单不外露。"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import repo
from .background import topup_in_background
from .deps import book_or_404, get_conn

router = APIRouter(prefix="/api/books/{book_id}", tags=["reading"])


class Progress(BaseModel):
    read_pos: int = Field(ge=0)


def _accepted(conn, book_id: int, idx: int) -> dict:
    ch = repo.get_chapter(conn, book_id, idx)
    if ch is None or ch["status"] != "accepted":
        raise HTTPException(404, "这一章还没写好")
    return ch


@router.get("/chapters")
def chapters(book_id: int, conn=Depends(get_conn)):
    book_or_404(conn, book_id)
    return [{"idx": c["idx"], "title": c["title"], "has_audio": repo.get_audio(conn, c["id"]) is not None}
            for c in repo.accepted_chapters(conn, book_id)]


@router.get("/chapters/{idx}")
def chapter(book_id: int, idx: int, conn=Depends(get_conn)):
    book_or_404(conn, book_id)
    ch = _accepted(conn, book_id, idx)
    has_audio = repo.get_audio(conn, ch["id"]) is not None
    return {"idx": idx, "title": ch["title"], "body": ch["body"],
            "audio_url": f"/api/books/{book_id}/chapters/{idx}/audio" if has_audio else None}


@router.get("/chapters/{idx}/audio")
def audio(book_id: int, idx: int, request: Request, conn=Depends(get_conn)):
    book_or_404(conn, book_id)
    rec = repo.get_audio(conn, _accepted(conn, book_id, idx)["id"])
    path = request.app.state.settings.audio_dir / rec["path"] if rec else None
    if path is None or not path.exists():
        raise HTTPException(404, "这一章的音频还没准备好")
    # FileResponse 自带 Range 支持:iOS 的 <audio> 必须能分段取流才能拖动/锁屏续播
    return FileResponse(path, media_type="audio/mpeg")


@router.put("/progress")
def progress(book_id: int, body: Progress, request: Request, tasks: BackgroundTasks, conn=Depends(get_conn)):
    book = book_or_404(conn, book_id)
    last = max((c["idx"] for c in repo.accepted_chapters(conn, book_id)), default=0)
    if body.read_pos > last:
        raise HTTPException(400, f"最多只能读到第 {last} 章")
    repo.update_book(conn, book_id, read_pos=body.read_pos)
    if book["status"] == "serializing":  # 读者往前读了 → 缓冲变薄 → 后台补货
        tasks.add_task(topup_in_background, request.app.state, book_id)
    return {"read_pos": body.read_pos}
