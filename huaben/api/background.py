"""请求结束后的后台补货。后台任务自己开连接(请求级连接此时可能已关闭)。"""
from ..db import connect
from ..llm import LLMError
from ..scheduler import top_up
from .deps import ensure_llm


def topup_in_background(state, book_id: int) -> None:
    try:
        llm = ensure_llm(state)
    except LLMError:
        return  # 没配密钥:无从补货;开书/读书接口本身已在前面把这件事告诉了用户
    conn = connect(state.settings.db_path, check_same_thread=False)
    try:
        # 补货失败已由 top_up 写进 books.gen_error,这里不会也不应再抛
        top_up(conn, llm, state.settings, book_id, tts=state.tts)
    finally:
        conn.close()
