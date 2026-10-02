"""书架:列表 / 新建 / 详情 / 统计。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .. import repo
from .deps import book_or_404, get_conn

router = APIRouter(prefix="/api/books", tags=["books"])


class NewBook(BaseModel):
    title: str = Field(default="未命名", max_length=100)


def book_view(conn, b: dict) -> dict:
    return {
        "id": b["id"], "title": b["title"], "genre": b["genre"], "status": b["status"],
        "read_pos": b["read_pos"],        # 读到的最远章
        "last_opened": b["last_opened"],  # 续读位置(最后打开/播放的章)
        "synopsis": b["synopsis"],
        "ready_chapters": repo.count_accepted(conn, b["id"]),
        "buffered_ahead": repo.buffered_ahead(conn, b["id"]),
        "gen_error": b["gen_error"],  # 非空 = 后台生成遇到问题,界面应提示
    }


@router.get("")
def list_books(conn=Depends(get_conn)):
    return [book_view(conn, b) for b in repo.list_books(conn)]


@router.post("", status_code=201)
def create_book(body: NewBook, conn=Depends(get_conn)):
    return book_view(conn, repo.get_book(conn, repo.create_book(conn, body.title)))


@router.get("/{book_id}")
def get_book(book_id: int, conn=Depends(get_conn)):
    return book_view(conn, book_or_404(conn, book_id))


@router.get("/{book_id}/stats")
def book_stats(book_id: int, conn=Depends(get_conn)):
    """可观测:单章平均成本/耗时/token(v0 验收要记录)。"""
    book_or_404(conn, book_id)
    return repo.cost_summary(conn, book_id)
