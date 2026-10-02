"""模型接口配置:网页"设置"页保存的值 + .env 的默认值 → 实际生效的配置。纯函数。

为什么要有网页设置(2026-10-02 用户要求):密钥原来只能登录服务器改 .env;用户要在网页里填,而且以后要换成
OpenCode 的 key。所以接口地址 / 模型名 / 密钥都可在页面上改,没填的项沿用 .env。
"""
from urllib.parse import urlparse

from .config import Settings

# 页面上的预设(2026-10-02 核对过 OpenCode 官方文档:Zen 的 OpenAI 兼容端点、模型 ID 不带厂商前缀)
PRESETS = {
    "openrouter": {"label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1",
                   "model": "deepseek/deepseek-v4.1-flash"},
    "opencode": {"label": "OpenCode Zen", "base_url": "https://opencode.ai/zen/v1", "model": "deepseek-v4.1-flash"},
}
KEYS = {"base_url": "openrouter_base_url", "api_key": "openrouter_api_key", "model": "llm_model"}


def effective(settings: Settings, saved: dict[str, str]) -> Settings:
    """saved:repo.get_app_settings 的结果(键为 base_url / api_key / model)。空值不覆盖。"""
    update = {field: saved[k] for k, field in KEYS.items() if saved.get(k)}
    return settings.model_copy(update=update) if update else settings


def is_openrouter(base_url: str) -> bool:
    """OpenRouter 才认识"关思考""回报费用"这两个扩展字段;发给别家可能被当作未知参数拒绝。"""
    host = urlparse(base_url).hostname or ""
    return host == "openrouter.ai" or host.endswith(".openrouter.ai")


def key_tail(key: str) -> str:
    """页面上只显示密钥末 4 位,完整密钥从不回传。"""
    return f"…{key[-4:]}" if len(key) >= 8 else ("已设置" if key else "")


def validate(values: dict[str, str]) -> str | None:
    """返回人话错误;None = 没问题。"""
    url = values.get("base_url")
    if url is not None and not url.startswith(("http://", "https://")):
        return "接口地址要以 http:// 或 https:// 开头"
    if "model" in values and not values["model"].strip():
        return "模型名不能为空"
    return None


def view(eff: Settings, saved: dict[str, str]) -> dict:
    """给设置页看的当前配置(不含密钥本身)。"""
    preset = next((k for k, p in PRESETS.items() if p["base_url"] == eff.openrouter_base_url), "custom")
    return {"base_url": eff.openrouter_base_url, "model": eff.llm_model, "preset": preset,
            "key_set": bool(eff.openrouter_api_key), "key_tail": key_tail(eff.openrouter_api_key),
            "key_from": "page" if saved.get("api_key") else ("env" if eff.openrouter_api_key else ""),
            "presets": PRESETS}
