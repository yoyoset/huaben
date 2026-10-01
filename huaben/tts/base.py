"""语音合成的窄接口。v1 的 PC GPU 工人是另一种实现/另一条升级路径,不改这里。"""
from typing import Protocol


class TTSError(Exception):
    """合成失败(网络/服务端/产物格式不对)。"""


class TTS(Protocol):
    def synthesize(self, text: str) -> bytes:
        """一小段文本 → MP3 字节。调用方负责切块;实现不得返回非 MP3。"""
        ...
