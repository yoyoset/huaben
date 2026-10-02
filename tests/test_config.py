"""配置校验:配错在启动那一刻说清楚,而不是运行中崩。"""
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from huaben.config import Settings, describe_config_error

ROOT = Path(__file__).resolve().parent.parent


def make(**kw):
    return Settings(_env_file=None, **kw)


def test_defaults_are_valid():
    s = make()
    assert s.buffer_chapters == 3 and s.openrouter_base_url == "https://openrouter.ai/api/v1"


@pytest.mark.parametrize("kw", [
    {"buffer_chapters": 0}, {"chapter_words": -5}, {"max_write_attempts": 0}, {"port": 70000},
    {"worker_interval_s": 0}, {"tts_retries": -1}, {"llm_model": ""}, {"openrouter_base_url": "openrouter.ai"},
])
def test_out_of_range_rejected(kw):
    with pytest.raises(ValidationError):
        make(**kw)


def test_cross_field_rules():
    with pytest.raises(ValidationError, match="BACKOFF_CAP_S"):
        make(backoff_base_s=600, backoff_cap_s=60)
    with pytest.raises(ValidationError, match="截断"):
        make(chapter_words=5000, chapter_max_tokens=3000)


def test_trailing_slash_trimmed():
    assert make(openrouter_base_url="https://x.example/api/").openrouter_base_url == "https://x.example/api"


def test_error_message_names_env_var_and_value():
    with pytest.raises(ValidationError) as ei:
        make(buffer_chapters=0, backoff_base_s=600, backoff_cap_s=60)
    msg = describe_config_error(ei.value)
    assert "HUABEN_BUFFER_CHAPTERS" in msg and "当前值:0" in msg
    assert "服务没有启动" in msg


def test_cross_field_error_message():
    with pytest.raises(ValidationError) as ei:
        make(backoff_base_s=600, backoff_cap_s=60)
    msg = describe_config_error(ei.value)
    assert "BACKOFF_CAP_S 不能小于 BACKOFF_BASE_S" in msg and "Value error" not in msg


def test_cli_exits_with_human_message_on_bad_config(tmp_path):
    """实测启动入口:坏配置 → 退出码 2 + 人话,不打堆栈。"""
    env = {"HUABEN_BUFFER_CHAPTERS": "0", "HUABEN_DATA_DIR": str(tmp_path), "PYTHONIOENCODING": "utf-8",
           "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")}
    r = subprocess.run([sys.executable, "-m", "huaben"], cwd=tmp_path, env={**env, "PYTHONPATH": str(ROOT)},
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 2
    assert "HUABEN_BUFFER_CHAPTERS" in r.stderr and "Traceback" not in r.stderr
