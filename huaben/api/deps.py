"""请求级依赖:每个请求一条独立 SQLite 连接;LLM/TTS 从 app.state 取(可注入,便于测试)。"""
from typing import Iterator

from fastapi import HTTPException, Request

from .. import repo
from ..db import connect
from ..human_errors import explain
from ..llm import LLM, LLMError, OpenRouterClient
from ..tts.base import TTS


def get_conn(request: Request) -> Iterator:
    # FastAPI 的同步依赖与端点可能落在不同线程;这条连接只服务当前请求,放宽线程检查是安全的
    conn = connect(request.app.state.settings.db_path, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()


def ensure_llm(state) -> LLM:
    """取 LLM;没注入就按配置惰性创建。没配密钥时抛 LLMError(调用方决定怎么告诉用户)。"""
    if state.llm is None:
        state.llm = OpenRouterClient(state.settings)
    return state.llm


def get_llm(request: Request) -> LLM:
    try:
        return ensure_llm(request.app.state)
    except LLMError as e:  # 没配密钥:明确告诉用户缺什么,而不是 500
        raise HTTPException(503, explain(e, auto_retry=False)) from e


def get_tts(request: Request) -> TTS | None:
    return request.app.state.tts


def book_or_404(conn, book_id: int) -> dict:
    book = repo.get_book(conn, book_id)
    if book is None:
        raise HTTPException(404, "书不存在")
    return book
