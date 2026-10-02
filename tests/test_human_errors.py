"""错误人话化:每类失败都告诉读者"发生了什么 + 要不要我做什么",且不夹带技术细节。"""
import httpx
import pytest

from huaben.config import Settings
from huaben.human_errors import MANUAL, explain
from huaben.llm import LLMEmptyError, LLMError, OpenRouterClient
from huaben.pipeline.errors import ChapterFailed
from huaben.tts.base import TTSError


@pytest.mark.parametrize("status,kind,needle", [
    (401, "auth", "密钥无效"), (403, "auth", "密钥无效"), (402, "quota", "余额不足"),
    (429, "rate_limit", "限流"), (503, "server", "暂时不可用"), (400, "request", "HUABEN_LLM_MODEL"),
])
def test_http_status_maps_to_kind_and_actionable_text(status, kind, needle):
    c = OpenRouterClient(Settings(openrouter_api_key="k", _env_file=None),
                         transport=httpx.MockTransport(lambda r: httpx.Response(status, text="raw-body")),
                         retries=0, sleep=lambda s: None)
    with pytest.raises(LLMError) as ei:
        c.chat([])
    assert ei.value.kind == kind and ei.value.status == status
    msg = explain(ei.value)
    assert needle in msg and "raw-body" not in msg and str(status) not in msg


def test_missing_key_and_empty_and_network():
    assert "HUABEN_OPENROUTER_API_KEY" in explain(LLMError("x", kind="no_key"))
    assert "空内容" in explain(LLMEmptyError("empty content (finish_reason=length)"))
    assert "网络" in explain(LLMError("x", kind="network"))


def test_chapter_failed_names_the_chapter():
    msg = explain(ChapterFailed("chapter 7 failed at write: 3 稿均未通过核对", step="write", idx=7))
    assert msg.startswith("第 7 章:连续几稿都没通过核对") and "自动重试" in msg


def test_interactive_actions_do_not_promise_auto_retry():
    msg = explain(LLMError("x", kind="server"), auto_retry=False)
    assert "自动重试" not in msg and MANUAL in msg


def test_unknown_exception_and_tts():
    assert "程序内部出错" in explain(KeyError("boom")) and "boom" not in explain(KeyError("boom"))
    assert "照常阅读" in explain(TTSError("x"))
