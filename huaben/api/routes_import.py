"""剧本制导入接口(T010):把架构方写好的 book.json 写进库。不做前端。"""
from fastapi import APIRouter, Body, Depends, HTTPException

from ..pipeline.parsing import ParseError
from ..script_import import ScriptImportError, import_book
from .deps import get_conn

router = APIRouter(tags=["import"])


@router.post("/api/import/book")
def import_book_route(body: dict = Body(...), conn=Depends(get_conn)):
    try:
        return {"book_id": import_book(conn, body)}
    except (ScriptImportError, ParseError) as e:
        raise HTTPException(400, str(e)) from e
