"""应用工厂。依赖(设置/LLM/TTS)都可注入,测试不碰网络。"""
from fastapi import FastAPI

from ..config import Settings, get_settings
from ..db import connect
from ..llm import LLM
from ..tts.base import TTS
from . import routes_books, routes_opening, routes_reading


def create_app(settings: Settings | None = None, llm: LLM | None = None, tts: TTS | None = None) -> FastAPI:
    app = FastAPI(title="话本 Huaben")
    app.state.settings = settings or get_settings()
    app.state.llm = llm  # None = 首次需要时按配置惰性创建
    app.state.tts = tts
    connect(app.state.settings.db_path).close()  # 启动时建库建表,第一个请求就能用
    app.include_router(routes_books.router)
    app.include_router(routes_opening.router)
    app.include_router(routes_reading.router)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app
