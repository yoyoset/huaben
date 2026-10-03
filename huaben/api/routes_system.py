"""系统状态:给部署探活与人工排查用。

- 只要服务和数据库能用就返回 200(docker healthcheck 依赖它);LLM 没配置不算"不健康",但要报告出来。
- 绝不回显密钥本身,只报告"配了没有"。
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from .. import __version__, repo
from ..budget import WINDOW_HOURS, spend_status, spent_recently
from ..db import connect
from ..migrate import current_version
from ..migrations import MIGRATIONS
from ..llm_config import is_subscription
from .deps import llm_settings

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
    eff = llm_settings(st)  # 网页「设置」里的值优先
    return {
        "ok": True,
        "version": __version__,
        "db": {"version": db_version, "latest": len(MIGRATIONS)},
        "worker": worker,
        "llm": {"configured": bool(eff.openrouter_api_key) or st.llm is not None,
                "model": eff.llm_model, "base_url": eff.openrouter_base_url},
        "tts": type(st.tts).__name__ if st.tts else None,
        # unpriced_calls > 0:上游没报费用,spent_usd 偏低、提醒与上限可能失灵(见 repo.unpriced_calls)
        "spend_24h": spend_status(spent, st.settings.spend_remind_usd_24h, st.settings.spend_limit_usd_24h, unpriced,
                                  is_subscription(eff.openrouter_base_url)),
    }


@router.get("/spend")
def spend(request: Request):
    """书架上的花费提醒用:只提醒、不拦(用户定的;硬上限默认关闭)。"""
    st = request.app.state.settings
    conn = connect(st.db_path, check_same_thread=False)
    try:
        return spend_status(spent_recently(conn), st.spend_remind_usd_24h, st.spend_limit_usd_24h,
                            repo.unpriced_calls(conn, hours=WINDOW_HOURS),
                            is_subscription(llm_settings(request.app.state).openrouter_base_url))
    finally:
        conn.close()


@router.get("/app/huaben.apk", include_in_schema=False)
def android_app(request: Request):
    """安卓 App 安装包(2026-10-03 用户要 APK:跑步前把章节 MP3 下到手机离线听)。
    包由 scripts/publish_apk.sh 放进 data/app/:它是构建产物,不进 git、也不打进镜像——更新 App 不必重建服务。"""
    path = request.app.state.settings.data_dir / "app" / "huaben.apk"
    if not path.is_file():
        raise HTTPException(404, "服务器上还没有安卓安装包")
    return FileResponse(path, media_type="application/vnd.android.package-archive", filename="huaben.apk")
