"""测试替身:不碰网络,返回合法的 MP3 头 + 文本字节,便于断言拼接顺序。"""
from .base import TTSError

FAKE_MP3_HEADER = b"ID3\x03\x00\x00\x00\x00\x00\x00"


class FakeTTS:
    def __init__(self, fail_times: int = 0, always_fail: bool = False):
        self.calls: list[str] = []
        self._fail_times = fail_times
        self._always_fail = always_fail

    def synthesize(self, text: str) -> bytes:
        self.calls.append(text)
        if self._always_fail or self._fail_times > 0:
            self._fail_times -= 1
            raise TTSError("fake tts failure")
        return FAKE_MP3_HEADER + text.encode("utf-8")
