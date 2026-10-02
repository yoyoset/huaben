"""系统状态:给部署探活与人工排查用。

- 只要服务和数据库能用就返回 200(docker healthcheck 依赖它);LLM 没配置不算"不健康",但要报告出来。
- 绝不回显密钥本身,只报告"配了没有"。
"""
from fastapi import APIRouter, Request

from .. import __version__, repo
from ..budget import WINDOW_HOURS, spent_recently
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
        # unpriced_calls > 0:上游没报费用,spent_usd 偏低、上限可能形同虚设(见 repo.unpriced_calls)
        "spend_24h": {"spent_usd": round(spent, 6), "limit_usd": st.settings.spend_limit_usd_24h,
                      "unpriced_calls": unpriced, "reliable": unpriced == 0},
    }
