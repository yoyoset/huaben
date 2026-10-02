"""EdgeTTS 适配层(路线 29):用替身 edge_tts 模块测,不碰网络、不需要装库。

关注点:挂住的连接必须在超时内变成 TTSError——否则会卡死唯一的后台线程。
"""
import asyncio
import sys
import time
import types

import pytest

from huaben.tts.base import TTSError
from huaben.tts.edge import EdgeTTS


def fake_edge_tts(monkeypatch, chunks=(), hang=False):
    class Communicate:
        def __init__(self, text, voice):
            self.text, self.voice = text, voice

        async def stream(self):
            if hang:
                await asyncio.sleep(3600)  # 模拟连接挂住、迟迟不来数据
            for c in chunks:
                yield c

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=Communicate))


def test_audio_chunks_are_joined(monkeypatch):
    fake_edge_tts(monkeypatch, [{"type": "audio", "data": b"ab"}, {"type": "WordBoundary"},
                                {"type": "audio", "data": b"cd"}])
    assert EdgeTTS().synthesize("一句。") == b"abcd"


def test_hanging_connection_times_out_as_tts_error(monkeypatch):
    fake_edge_tts(monkeypatch, hang=True)
    t0 = time.monotonic()
    with pytest.raises(TTSError, match="超过"):
        EdgeTTS(timeout_s=0.2).synthesize("一句。")
    assert time.monotonic() - t0 < 2  # 在超时附近返回,而不是一直卡住


def test_empty_audio_is_an_error(monkeypatch):
    fake_edge_tts(monkeypatch, [{"type": "WordBoundary"}])
    with pytest.raises(TTSError, match="空音频"):
        EdgeTTS().synthesize("一句。")
