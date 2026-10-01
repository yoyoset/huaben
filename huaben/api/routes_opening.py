"""开书:对话记录 / 说一句 / 定稿开书。"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import repo
from ..llm import LLMError
from ..opening.service import OpeningError, finalize_book, opening_turn
from ..pipeline.errors import ChapterFailed
from .background import topup_in_background
from .deps import book_or_404, get_conn, get_llm
from .routes_books import book_view

router = APIRouter(prefix="/api/books/{book_id}", tags=["opening"])


class Say(BaseModel):
    message: str = Field(min_length=1, max_length=20000)  # 读者会粘贴整段样章,留足长度


@router.get("/opening")
def history(book_id: int, conn=Depends(get_conn)):
    book_or_404(conn, book_id)
    return repo.list_messages(conn, book_id)


@router.post("/opening")
def say(book_id: int, body: Say, conn=Depends(get_conn), llm=Depends(get_llm)):
    book_or_404(conn, book_id)
    try:
        return opening_turn(conn, llm, book_id, body.message)
    except OpeningError as e:
        raise HTTPException(400, str(e)) from e
    except LLMError as e:
        raise HTTPException(502, f"模型暂时不可用:{e}") from e


@router.post("/finalize")
def finalize(book_id: int, request: Request, tasks: BackgroundTasks, conn=Depends(get_conn), llm=Depends(get_llm)):
    book_or_404(conn, book_id)
    try:
        book = finalize_book(conn, llm, request.app.state.settings, book_id)
    except OpeningError as e:
        raise HTTPException(400, str(e)) from e
    except (LLMError, ChapterFailed) as e:
        raise HTTPException(502, f"开书没成功,可以重试:{e}") from e
    tasks.add_task(topup_in_background, request.app.state, book_id)  # 开书即开始预生成
    return book_view(conn, book)
