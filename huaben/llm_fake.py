"""测试替身:不碰网络的 LLM。流水线/API 测试用它注入。"""
from .llm import LLMResult


class FakeLLM:
    """测试用:按顺序吐预设回复,并记录收到的 messages。"""

    def __init__(self, replies: list[str | LLMResult | Exception]):
        self._replies = list(replies)
        self.calls: list[list[dict]] = []

    def chat(self, messages, *, max_tokens=None, temperature=0.9, json_mode=False) -> LLMResult:
        self.calls.append(messages)
        if not self._replies:
            raise AssertionError("FakeLLM: 没有预设回复了")
        r = self._replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, LLMResult) else LLMResult(text=r, tokens_in=100, tokens_out=200, cost_usd=0.001)
