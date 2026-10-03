"""剧本制导入接口(T010/T011):把架构方写好的 book.json / 卷剧本写进库。不做前端。"""
from fastapi import APIRouter, Body, Depends, HTTPException, Request

from ..human_errors import explain
from ..llm import LLMError
from ..pipeline.errors import ChapterFailed
from ..pipeline.parsing import ParseError
from ..script_import import ScriptImportError, import_book, import_volume
from .deps import get_conn, get_llm

router = APIRouter(tags=["import"])


@router.post("/api/import/book")
def import_book_route(body: dict = Body(...), conn=Depends(get_conn)):
    try:
        return {"book_id": import_book(conn, body)}
    except (ScriptImportError, ParseError) as e:
        raise HTTPException(400, str(e)) from e


@router.post("/api/books/{book_id}/import/volume")
def import_volume_route(book_id: int, request: Request, body: dict = Body(...),
                        conn=Depends(get_conn), llm=Depends(get_llm)):
    try:
        return import_volume(conn, llm, request.app.state.settings, book_id, body)
    except ScriptImportError as e:
        raise HTTPException(400, detail=e.problems) from e
    except (LLMError, ChapterFailed) as e:
        raise HTTPException(502, explain(e, auto_retry=False)) from e
