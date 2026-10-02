"""每本书的写法设定:开书时选模板,开书后随时改(下一章起生效)。选项与默认值见 huaben/craft.py。"""
import json

from fastapi import APIRouter, Body, Depends

from .. import repo
from ..craft import from_book, normalize_craft, options_view
from .deps import book_or_404, get_conn

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
