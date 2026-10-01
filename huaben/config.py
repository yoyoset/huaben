"""配置层:唯一的参数来源。环境变量 HUABEN_* 或 .env,代码里不散落硬编码。"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HUABEN_", env_file=".env", extra="ignore")

    data_dir: Path = Path("./data")
    web_dir: Path = Path(__file__).resolve().parent.parent / "web"  # PWA 静态文件

    # LLM(默认值见 CLAUDE.md:长文生成关思考、两项惩罚为 0)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "deepseek/deepseek-v4.1-flash"
    llm_timeout_s: float = 180.0
    chapter_max_tokens: int = 8000  # 3000 字约 4~6k token,留足余量
    chapter_words: int = 2500  # 单章目标字数
    max_write_attempts: int = 3  # 正文被打回/截断/解析失败时最多写几稿

    # 连载
    buffer_chapters: int = 3  # 比读者进度多备几章
    recent_chapters_in_prompt: int = 3

    # 服务与后台循环
    host: str = "0.0.0.0"
    port: int = 8000
    worker_enabled: bool = True
    worker_interval_s: float = 60.0   # 后台每隔多久巡检一遍所有连载中的书
    backoff_base_s: float = 60.0      # 某本书补货失败后,首次等多久再试;之后每次翻倍
    backoff_cap_s: float = 1800.0

    # 保底语音
    tts_voice: str = "zh-CN-XiaoxiaoNeural"
    tts_chunk_chars: int = 1500  # 长章按段落切块合成再拼接,单次请求不过长
    tts_retries: int = 2

    @property
    def db_path(self) -> Path:
        return self.data_dir / "huaben.db"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"


@lru_cache
def get_settings() -> Settings:
    return Settings()
