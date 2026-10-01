"""Edge TTS 真实现(Python edge-tts 库,不走酒馆插件)。

注意:需要 `pip install edge-tts` 与能访问 speech.platform.bing.com 的网络(13 上 2026-09-28 实测可直连)。
内部用 asyncio.run,只能在没有运行中事件循环的线程里调用(调度器在后台线程,满足)。
**未实测**:本机未装 edge-tts,下列假设待首次真实运行核对 —— 库默认输出就是
24kHz/48kbps 单声道 MP3(由 service 层的 is_mp3 把关,不对会显式失败而不是静默入库)。
"""
import asyncio

from .base import TTSError


class EdgeTTS:
    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural"):
        self.voice = voice

    def synthesize(self, text: str) -> bytes:
        try:
            return asyncio.run(self._stream(text))
        except TTSError:
            raise
        except Exception as e:  # edge-tts 抛的异常种类多(网络/协议),统一成 TTSError
            raise TTSError(f"{type(e).__name__}: {e}") from e

    async def _stream(self, text: str) -> bytes:
        import edge_tts  # 惰性导入:没装库时其它模块与测试照常工作

        buf = bytearray()
        async for chunk in edge_tts.Communicate(text, self.voice).stream():
            if chunk["type"] == "audio":
                buf += chunk["data"]
        if not buf:
            raise TTSError("edge-tts 返回了空音频")
        return bytes(buf)
