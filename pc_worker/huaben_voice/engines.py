"""TTS 引擎:窄接口 + 注册表。kokoro-zh(快、音色一般)/ qwen3-zh(音质好,要 .venv-qwen),见 README。

接口:synthesize(text) -> MP3 bytes。长章怎么切块、用什么音色,都是引擎自己的事——不同模型的单次长度上限不同。
"""
from typing import Callable, Protocol


class Engine(Protocol):
    def synthesize(self, text: str) -> bytes: ...


class FakeEngine:
    """测试与"空跑"用:返回合法的 MP3 帧(长度随文本变化),不需要 GPU、不需要模型。"""

    FRAME = bytes([0xFF, 0xFB, 0x90, 0x00]) + bytes(413)

    def __init__(self):
        self.calls: list[str] = []

    def synthesize(self, text: str) -> bytes:
        self.calls.append(text)
        return self.FRAME * max(1, len(text) // 10)


def _kokoro_zh(**opts) -> Engine:
    from .kokoro_zh import KokoroZh  # 惰性:没装 torch/kokoro 时 fake 引擎与测试照常可用
    return KokoroZh(**opts)


def _qwen3_zh(**opts) -> Engine:
    from .qwen3_zh import Qwen3Zh  # 惰性:只在 .venv-qwen 里装了依赖
    return Qwen3Zh(**opts)


ENGINES: dict[str, Callable[..., Engine]] = {"fake": lambda **_: FakeEngine(), "kokoro-zh": _kokoro_zh,
                                             "qwen3-zh": _qwen3_zh}


def create_engine(name: str, **opts) -> Engine:
    """opts:引擎参数(如 voice、speed);fake 忽略。"""
    if name not in ENGINES:
        raise ValueError(f"未知的 TTS 引擎 {name!r},可用:{sorted(ENGINES)}")
    return ENGINES[name](**opts)
