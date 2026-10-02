"""配置层:唯一的参数来源。环境变量 HUABEN_* 或 .env,代码里不散落硬编码。

每个数值都有范围校验:配错时在**启动那一刻**给出人话错误(哪个环境变量、为什么不行),
而不是带着坏配置跑起来、到生成第 N 章时才崩。
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "HUABEN_"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, env_file=".env", extra="ignore")

    data_dir: Path = Path("./data")
    web_dir: Path = Path(__file__).resolve().parent.parent / "web"  # PWA 静态文件

    # LLM(默认值见 CLAUDE.md:长文生成关思考、两项惩罚为 0)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = Field("deepseek/deepseek-v4.1-flash", min_length=1)
    llm_timeout_s: float = Field(180.0, gt=0, le=1800)
    chapter_max_tokens: int = Field(8000, ge=256, le=200_000)  # 3000 字约 4~6k token,留足余量
    chapter_words: int = Field(2500, ge=1, le=20_000)          # 单章目标字数
    max_write_attempts: int = Field(3, ge=1, le=10)            # 正文被打回/截断/解析失败时最多写几稿
    # 花费安全阀:滚动 24 小时、全部书合计;0 = 不设上限。默认值按 flash 模型单章约 1~2 美分估算,
    # 约等于一天写 100+ 章——正常使用碰不到,只拦失控。见 huaben/budget.py
    spend_limit_usd_24h: float = Field(2.0, ge=0)

    # 连载
    buffer_chapters: int = Field(3, ge=1, le=50)               # 比读者进度多备几章
    recent_chapters_in_prompt: int = Field(3, ge=0, le=20)

    # 服务与后台循环
    host: str = "0.0.0.0"
    port: int = Field(8000, ge=1, le=65535)
    worker_enabled: bool = True
    worker_interval_s: float = Field(60.0, gt=0)   # 后台每隔多久巡检一遍所有连载中的书
    backoff_base_s: float = Field(60.0, gt=0)      # 某本书补货失败后,首次等多久再试;之后每次翻倍
    backoff_cap_s: float = Field(1800.0, gt=0)

    # 保底语音
    tts_voice: str = Field("zh-CN-XiaoxiaoNeural", min_length=1)
    tts_chunk_chars: int = Field(1500, ge=1, le=10_000)  # 长章按段落切块合成再拼接,单次请求不过长
    tts_retries: int = Field(2, ge=0, le=10)

    @field_validator("openrouter_base_url")
    @classmethod
    def _http_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("必须以 http:// 或 https:// 开头")
        return v.rstrip("/")

    @model_validator(mode="after")
    def _consistent(self) -> "Settings":
        if self.backoff_cap_s < self.backoff_base_s:
            raise ValueError("BACKOFF_CAP_S 不能小于 BACKOFF_BASE_S")
        # 中文约 1~1.5 token/字;max_tokens 连目标字数都不够,每章都会被截断、写满几稿后失败
        if self.chapter_max_tokens < self.chapter_words:
            raise ValueError("CHAPTER_MAX_TOKENS 小于 CHAPTER_WORDS,一章写不完就会被截断")
        return self

    @property
    def db_path(self) -> Path:
        return self.data_dir / "huaben.db"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"


def describe_config_error(exc: ValidationError) -> str:
    """把 pydantic 的校验错误翻译成"哪个环境变量、为什么不行"。"""
    lines = ["配置有误,服务没有启动。请检查 .env 或环境变量:"]
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", ()) if x != "__root__"]
        name = f"{ENV_PREFIX}{loc[0].upper()}" if loc else "(多个配置之间)"
        msg = err.get("msg", "").removeprefix("Value error, ")
        given = err.get("input")
        shown = f"(当前值:{given!r})" if loc and not isinstance(given, dict) else ""
        lines.append(f"- {name}:{msg}{shown}")
    return "\n".join(lines)


@lru_cache
def get_settings() -> Settings:
    return Settings()
