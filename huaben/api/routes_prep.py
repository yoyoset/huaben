"""出门前预备 N 章:正文写好 + 音频配好,手机 App 据此把 MP3 下到本地离线听。规则见 huaben/prep.py。

- POST /api/books/{id}/prepare {"count": 10}  从当前章起预备 count 章,立刻开始补写
- GET  /api/books/{id}/prepare                 进度,以及范围内每章的音频地址(App 下载用)
"""
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field

from .. import repo
from ..prep import MAX_PREP, prep_range, prep_view
from ..tts.store import best_playable, index_paths
from .background import topup_in_background
from .deps import book_or_404, get_conn

router = APIRouter(prefix="/api/books/{book_id}/prepare", tags=["prepare"])


class PrepIn(BaseModel):
    count: int = Field(ge=1, le=MAX_PREP)


def _view(conn, settings, book: dict) -> dict:
    start = max(1, book["last_opened"])
    end = max(book["prep_until"], start)
    rows = repo.chapter_index(conn, book["id"], idx_from=start, idx_to=end)
    chapters = []
    for c in rows:
        rel = best_playable(settings, index_paths(c))
        chapters.append({"idx": c["idx"], "title": c["title"], "has_audio": rel is not None,
                         # 地址带上是哪一份文件:换了音色/从 edge 换成电脑版后地址会变,App 据此知道要重新下
                         "audio_url": f"/api/books/{book['id']}/chapters/{c['idx']}/audio?v={rel.replace('/', '_')}"
                         if rel else None})
    return {**prep_view(start, end, chapters), "active": book["prep_until"] >= start}


@router.post("")
def prepare(book_id: int, body: PrepIn, request: Request, tasks: BackgroundTasks, conn=Depends(get_conn)):
    book = book_or_404(conn, book_id)
    _, end = prep_range(book["last_opened"], body.count)
    repo.update_book(conn, book_id, prep_until=end)
    tasks.add_task(topup_in_background, request.app.state, book_id)  # 不等下一次巡检(最长一分钟)
    return _view(conn, request.app.state.settings, repo.get_book(conn, book_id))


@router.get("")
def status(book_id: int, request: Request, conn=Depends(get_conn)):
    return _view(conn, request.app.state.settings, book_or_404(conn, book_id))
