"""书架:列表 / 新建 / 详情 / 统计。"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from .. import repo, stats
from .deps import book_or_404, get_conn

router = APIRouter(prefix="/api/books", tags=["books"])


class NewBook(BaseModel):
    title: str = Field(default="未命名", max_length=100)


def book_view(conn, b: dict, buffer_target: int) -> dict:
    """buffer_target:预生成缓冲目标章数。generating = 后台还会继续补货,前端据此决定要不要自动刷新。"""
    buffered = repo.buffered_ahead(conn, b["id"])
    return {
        "id": b["id"], "title": b["title"], "genre": b["genre"], "status": b["status"],
        "read_pos": b["read_pos"],        # 读到的最远章
        "last_opened": b["last_opened"],  # 续读位置(最后打开/播放的章)
        "synopsis": b["synopsis"],
        "ready_chapters": repo.count_accepted(conn, b["id"]),
        "buffered_ahead": buffered,
        "generating": b["status"] == "serializing" and buffered < buffer_target,
        "gen_error": b["gen_error"],  # 非空 = 后台生成遇到问题,界面应提示
    }


@router.get("")
def list_books(request: Request, conn=Depends(get_conn)):
    target = request.app.state.settings.buffer_chapters
    return [book_view(conn, b, target) for b in repo.list_books(conn)]


@router.post("", status_code=201)
def create_book(body: NewBook, request: Request, conn=Depends(get_conn)):
    book = repo.get_book(conn, repo.create_book(conn, body.title))
    return book_view(conn, book, request.app.state.settings.buffer_chapters)


@router.get("/{book_id}")
def get_book(book_id: int, request: Request, conn=Depends(get_conn)):
    return book_view(conn, book_or_404(conn, book_id), request.app.state.settings.buffer_chapters)


@router.get("/{book_id}/stats")
def book_stats(book_id: int, conn=Depends(get_conn)):
    """可观测:单章平均成本/耗时、重写率、配音覆盖、失败分布(口径见 huaben/stats.py)。"""
    book_or_404(conn, book_id)
    return stats.book_stats(conn, book_id)
