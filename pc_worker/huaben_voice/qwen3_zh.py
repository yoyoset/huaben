"""引擎:Qwen3-TTS 1.7B(阿里通义,Apache-2.0),经 faster-qwen3-tts(MIT)用 CUDA graph 加速。

为什么换(2026-10-02 用户):Kokoro 的音色不行,3060 应该跑得动更好的。Qwen3-TTS 有内置中文音色、能用一句话"设计"音色、
能按指令调语气,显存 6~8GB 档。
实测(RTX 3060 12GB,Windows,同一段 13 秒的正文):
- 官方 qwen-tts 直接跑:0.12 倍实时(94 秒音频要 762 秒),释放显存后依旧——每一步解码约 500 次小 kernel 启动,
  Windows 上启动开销压倒了计算,不是显存问题(最初以为是 Kokoro 占着显存,实测排除);
- faster-qwen3-tts(把一步解码录成 CUDA graph 重放):1.8 倍实时,峰值显存 4.9GB。一章 10 分钟音频约 5~6 分钟配完。
依赖装在单独的 .venv-qwen:要 transformers 5.15.x,与 Kokoro 用的 4.x 冲突。见 requirements-qwen.txt。
"""
from .kokoro_zh import encode_mp3, segments  # 切段与编码两个引擎通用

CUSTOM_REPO = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
DESIGN_REPO = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
DESIGN_PREFIX = "设计:"      # voice 以它开头 = 用一句话描述音色(VoiceDesign 模型),否则是内置音色名
MAX_SEG_CHARS = 200          # 太长的一次生成容易语气漂移、偶发吞字;按句拼到 200 字以内
PARAGRAPH_PAUSE_S = 0.5


def speed_hint(speed: float) -> str:
    """Qwen3-TTS 没有语速参数,只能用指令说。纯函数。"""
    if speed >= 1.15:
        return "语速稍快"
    if speed <= 0.85:
        return "语速稍慢"
    return ""


class Qwen3Zh:
    def __init__(self, voice: str = "Uncle_Fu", speed: float = 1.0, instruct: str = ""):
        import numpy as np
        from faster_qwen3_tts import FasterQwen3TTS  # 惰性导入:服务器端与测试环境没有这些依赖

        self._np = np
        self.design = voice.startswith(DESIGN_PREFIX)
        self.voice = voice[len(DESIGN_PREFIX):] if self.design else voice
        self.instruct = ",".join(x for x in (instruct, speed_hint(speed)) if x)
        self.model = FasterQwen3TTS.from_pretrained(DESIGN_REPO if self.design else CUSTOM_REPO)

    def _say(self, seg: str):
        if self.design:  # 设计音色:描述本身就是指令,语气/语速要求接在后面
            wavs, sr = self.model.generate_voice_design(text=seg, language="Chinese",
                                                        instruct=",".join(x for x in (self.voice, self.instruct) if x))
        else:
            wavs, sr = self.model.generate_custom_voice(text=seg, language="Chinese", speaker=self.voice,
                                                        **({"instruct": self.instruct} if self.instruct else {}))
        return self._np.concatenate([self._np.asarray(w, dtype="float32").reshape(-1) for w in wavs]), sr

    def synthesize(self, text: str) -> bytes:
        np, chunks, sr = self._np, [], 24000
        for para in segments(text, MAX_SEG_CHARS):
            for seg in para:
                audio, sr = self._say(seg)
                chunks.append(audio)
            chunks.append(np.zeros(int(sr * PARAGRAPH_PAUSE_S), dtype="float32"))
        if not chunks:
            raise ValueError("没有可朗读的文本")
        return encode_mp3(np.concatenate(chunks), sr)
