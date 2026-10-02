"""请求结束后的后台补货。后台任务自己开连接(请求级连接此时可能已关闭)。"""
from ..db import connect
from ..llm import LLMError
from .. import repo
from ..scheduler import top_up
from ..tts.service import voice_fallback
from .deps import auto_tts, ensure_llm


def topup_in_background(state, book_id: int) -> None:
    try:
        llm = ensure_llm(state)
    except LLMError:
        return  # 没配密钥:无从补货;开书/读书接口本身已在前面把这件事告诉了用户
    conn = connect(state.settings.db_path, check_same_thread=False)
    try:
        # 补货失败已由 top_up 写进 books.gen_error,这里不会也不应再抛
        top_up(conn, llm, state.settings, book_id, tts=auto_tts(state))
    finally:
        conn.close()


def voice_fallback_in_background(state, book_id: int) -> None:
    """用户手动选的"先用 edge-tts 配"。失败写进 audio_error(界面可见),不抛。"""
    conn = connect(state.settings.db_path, check_same_thread=False)
    try:
        pos = max(1, repo.get_book(conn, book_id)["last_opened"])
        _, err = voice_fallback(conn, state.tts, state.settings, book_id, pos)
        repo.update_book(conn, book_id, audio_error=err)
    finally:
        conn.close()
