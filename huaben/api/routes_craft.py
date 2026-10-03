"""每本书的写法设定:开书时选模板,开书后随时改(下一章起生效)。选项与默认值见 huaben/craft.py。"""
import json

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from .. import repo
from ..craft import from_book, normalize_craft, options_view
from ..human_errors import explain
from ..llm import LLMError
from ..pipeline.errors import ChapterFailed
from ..pipeline.jsonout import ParseError
from ..pipeline.rebudget import rebudget
from ..pipeline.volume import fill_arc
from ..pipeline.world_expand import expand_world
from .deps import book_or_404, get_conn, get_llm

router = APIRouter(tags=["craft"])


@router.get("/api/craft/options")
def options():
    return options_view()


@router.get("/api/books/{book_id}/craft")
def get_craft(book_id: int, conn=Depends(get_conn)):
    return from_book(book_or_404(conn, book_id))


@router.put("/api/books/{book_id}/craft")
def save_craft(book_id: int, body: dict = Body(...), conn=Depends(get_conn)):
    """认不出的选项按默认值存(不报错):页面只会发选项里有的值,这里只是兜底。"""
    book_or_404(conn, book_id)
    craft = normalize_craft(body)
    repo.update_book(conn, book_id, craft=json.dumps(craft, ensure_ascii=False))
    return craft


@router.post("/api/books/{book_id}/world/expand")
def expand(book_id: int, conn=Depends(get_conn), llm=Depends(get_llm)):
    """给已开书的书补充原创设定(只加不改,见 pipeline/world_expand.py)。一次模型调用,通常十几秒。"""
    book = book_or_404(conn, book_id)
    if book["status"] == "drafting":
        raise HTTPException(409, "还没开书:开书时会按「想象力」设定直接搭世界观,不用补充")
    try:
        return expand_world(conn, llm, book_id)
    except (LLMError, ParseError) as e:
        raise HTTPException(502, explain(e, auto_retry=False)) from e


@router.post("/api/books/{book_id}/volume/arc")
def volume_arc(book_id: int, request: Request, conn=Depends(get_conn), llm=Depends(get_llm)):
    """给进行中的卷补"一段征战"的结构(旧书升级用;新卷规划时就带着)。一次模型调用。"""
    book_or_404(conn, book_id)
    try:
        return fill_arc(conn, llm, request.app.state.settings, book_id)
    except (LLMError, ChapterFailed) as e:
        raise HTTPException(502, explain(e, auto_retry=False)) from e


@router.post("/api/books/{book_id}/volume/budget")
def volume_budget(book_id: int, request: Request, conn=Depends(get_conn), llm=Depends(get_llm)):
    """给进行中的卷补每个节拍的章数预算(旧书升级用;新卷规划时就带着)。一次模型调用,下一章起生效。"""
    book_or_404(conn, book_id)
    try:
        return rebudget(conn, llm, request.app.state.settings, book_id)
    except (LLMError, ChapterFailed) as e:
        raise HTTPException(502, explain(e, auto_retry=False)) from e
