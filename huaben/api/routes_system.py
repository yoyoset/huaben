"""系统状态:给部署探活与人工排查用。

- 只要服务和数据库能用就返回 200(docker healthcheck 依赖它);LLM 没配置不算"不健康",但要报告出来。
- 绝不回显密钥本身,只报告"配了没有"。
"""
from fastapi import APIRouter, Request

from .. import __version__, repo
from ..budget import WINDOW_HOURS, spend_status, spent_recently
from ..db import connect
from ..migrate import current_version
from ..migrations import MIGRATIONS

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(request: Request):
    st = request.app.state
    conn = connect(st.settings.db_path, check_same_thread=False)
    try:
        db_version = current_version(conn)
        spent = spent_recently(conn)
        unpriced = repo.unpriced_calls(conn, hours=WINDOW_HOURS)
    finally:
        conn.close()
    worker = st.worker.status() if st.worker else {"enabled": False}
    return {
        "ok": True,
        "version": __version__,
        "db": {"version": db_version, "latest": len(MIGRATIONS)},
        "worker": worker,
        "llm": {"configured": bool(st.settings.openrouter_api_key) or st.llm is not None,
                "model": st.settings.llm_model},
        "tts": type(st.tts).__name__ if st.tts else None,
        # unpriced_calls > 0:上游没报费用,spent_usd 偏低、提醒与上限可能失灵(见 repo.unpriced_calls)
        "spend_24h": spend_status(spent, st.settings.spend_remind_usd_24h, st.settings.spend_limit_usd_24h, unpriced),
    }


@router.get("/spend")
def spend(request: Request):
    """书架上的花费提醒用:只提醒、不拦(用户定的;硬上限默认关闭)。"""
    st = request.app.state.settings
    conn = connect(st.db_path, check_same_thread=False)
    try:
        return spend_status(spent_recently(conn), st.spend_remind_usd_24h, st.spend_limit_usd_24h,
                            repo.unpriced_calls(conn, hours=WINDOW_HOURS))
    finally:
        conn.close()
