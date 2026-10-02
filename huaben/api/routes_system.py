"""系统状态:给部署探活与人工排查用。

- 只要服务和数据库能用就返回 200(docker healthcheck 依赖它);LLM 没配置不算"不健康",但要报告出来。
- 绝不回显密钥本身,只报告"配了没有"。
"""
from fastapi import APIRouter, Request

from .. import __version__
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
    }
