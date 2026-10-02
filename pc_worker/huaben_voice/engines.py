"""TTS 引擎:窄接口 + 注册表。真实的中文模型等出样音、用户试听定下来之后再加(见 README)。

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


ENGINES: dict[str, Callable[[], Engine]] = {"fake": FakeEngine}


def create_engine(name: str) -> Engine:
    if name not in ENGINES:
        raise ValueError(f"未知的 TTS 引擎 {name!r},可用:{sorted(ENGINES)}")
    return ENGINES[name]()
