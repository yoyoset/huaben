"""网页「设置」:模型接口地址 / 模型名 / 密钥(2026-10-02 用户要求:在网页里填 key,以后换成 OpenCode 的 key)。

- 密钥只进不出:GET 只返回"设没设、末 4 位",完整密钥从不回传。
- 保存后清掉缓存的模型客户端,下一次调用按新配置重建——不用重启服务。
- "测试连接"真的发一次很小的请求(几个 token),当场告诉用户密钥/地址/模型对不对。
"""
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import repo
from ..human_errors import explain
from ..llm import LLMError, OpenRouterClient
from ..llm_config import validate, view
from .deps import get_conn, llm_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsIn(BaseModel):
    base_url: str | None = Field(default=None, max_length=300)
    model: str | None = Field(default=None, max_length=200)
    api_key: str | None = Field(default=None, max_length=500)  # 空 = 不改


@router.get("")
def get_settings(request: Request, conn=Depends(get_conn)):
    return view(llm_settings(request.app.state), repo.get_app_settings(conn))


@router.put("")
def save_settings(body: SettingsIn, request: Request, conn=Depends(get_conn)):
    values = {k: v.strip() for k, v in body.model_dump().items() if v is not None and v.strip()}
    err = validate(values)
    if err:
        raise HTTPException(400, err)
    repo.set_app_settings(conn, values)
    state = request.app.state
    if not getattr(state, "llm_injected", False):  # 测试注入的替身不动;真实客户端按新配置重建
        state.llm = None
    return view(llm_settings(state), repo.get_app_settings(conn))


@router.post("/test")
def test_connection(request: Request):
    state = request.app.state
    st = llm_settings(state)
    t0 = time.monotonic()
    try:
        client = OpenRouterClient(st, transport=getattr(state, "llm_transport", None), retries=0)
        res = client.chat([{"role": "user", "content": "只回复两个字:收到"}], max_tokens=200, temperature=0)
    except LLMError as e:
        return {"ok": False, "error": explain(e, auto_retry=False), "detail": str(e)[:300]}
    return {"ok": True, "model": st.llm_model, "reply": res.text.strip()[:50],
            "ms": int((time.monotonic() - t0) * 1000), "cost_reported": res.cost_usd > 0}
