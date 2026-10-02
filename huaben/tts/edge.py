"""Edge TTS 真实现(Python edge-tts 库,不走酒馆插件)。

注意:需要 `pip install edge-tts` 与能访问 speech.platform.bing.com 的网络(13 上 2026-09-28 实测可直连)。
内部用 asyncio.run,只能在没有运行中事件循环的线程里调用(调度器在后台线程,满足)。
**未实测**:本机未装 edge-tts,下列假设待首次真实运行核对 —— 库默认输出就是
24kHz/48kbps 单声道 MP3(由 service 层的 is_mp3 把关,不对会显式失败而不是静默入库)。
"""
import asyncio

from .base import TTSError


class EdgeTTS:
    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural", timeout_s: float = 120.0):
        self.voice = voice
        # 自己设总超时,不依赖库:requirements 只写了 edge-tts>=6,各版本的内置超时不一定有、默认值也不同。
        # 没有超时时,一次挂住的连接会卡死唯一的后台线程——所有书的文字补货都跟着停
        self.timeout_s = timeout_s

    def synthesize(self, text: str) -> bytes:
        try:
            return asyncio.run(asyncio.wait_for(self._stream(text), self.timeout_s))
        except TTSError:
            raise
        except (asyncio.TimeoutError, TimeoutError) as e:
            raise TTSError(f"配音请求超过 {self.timeout_s:g} 秒没有完成") from e
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
