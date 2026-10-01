"""应用工厂。依赖(设置/LLM/TTS)都可注入,测试不碰网络。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..config import Settings, get_settings
from ..db import connect
from ..llm import LLM
from ..tts.base import TTS
from ..worker import Backoff, Worker
from . import routes_books, routes_opening, routes_reading


def create_app(settings: Settings | None = None, llm: LLM | None = None, tts: TTS | None = None) -> FastAPI:
    st = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        worker = None
        if st.worker_enabled:
            worker = Worker(app.state, st.worker_interval_s, Backoff(st.backoff_base_s, st.backoff_cap_s))
            worker.start()
        yield
        if worker:
            worker.stop()

    app = FastAPI(title="话本 Huaben", lifespan=lifespan)
    app.state.settings = st
    app.state.llm = llm  # None = 首次需要时按配置惰性创建
    app.state.tts = tts
    connect(st.db_path).close()  # 启动时建库建表,第一个请求就能用
    app.include_router(routes_books.router)
    app.include_router(routes_opening.router)
    app.include_router(routes_reading.router)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    if st.web_dir.is_dir():  # 必须最后挂载:/ 兜底静态文件,不能盖住上面的 /api 路由
        app.mount("/", StaticFiles(directory=st.web_dir, html=True), name="web")
    return app
