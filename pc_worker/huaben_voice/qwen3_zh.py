"""引擎:Qwen3-TTS 1.7B(阿里通义,Apache-2.0),经 faster-qwen3-tts(MIT)用 CUDA graph 加速;**克隆一段固定参考音**。

为什么换(2026-10-02 用户):Kokoro 的音色不行,3060 应该跑得动更好的。
速度(RTX 3060 12GB,Windows):官方 qwen-tts 0.12 倍实时,每步解码约 500 次小 kernel 启动、Windows 上启动开销压倒计算
(不是显存问题,释放显存后实测一样);faster-qwen3-tts 1.8 倍实时,一章 10 分钟音频约 5~6 分钟。

为什么是"克隆参考音"而不是内置音色/一句话设计音色(2026-10-03 用户试听:音色前后不一致,对白被读成评书腔):
一章要切成几十段分别合成,内置音色和设计音色每一段都是模型现场"想"出来的声音,段与段之间会漂。实测同一段 4 段正文,
每段音高中位数:Serena 内置 241/269/204/251 Hz(极差 66),设计的评书男声 87/260/157/180 Hz(极差 173,像换了人);
改成每段都克隆同一段 10 秒参考音后:女 236~277(41)、男 174~208(34)。
参考音放在 pc_worker/voices/<名字>.wav,旁边的 <名字>.txt 是参考音里说的话(克隆要用)。

依赖装在单独的 .venv-qwen:要 transformers 5.15.x,与 Kokoro 用的 4.x 冲突。见 requirements-qwen.txt。
"""
from pathlib import Path

from .kokoro_zh import encode_mp3, segments  # 切段与编码两个引擎通用

BASE_REPO = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
VOICES_DIR = Path(__file__).resolve().parent.parent / "voices"
MAX_SEG_CHARS = 200          # 太长的一次生成容易语气漂移、偶发吞字;按句拼到 200 字以内
PARAGRAPH_PAUSE_S = 0.5


def reference(voice: str, voices_dir: Path = VOICES_DIR) -> tuple[Path, str]:
    """音色名 → (参考音文件, 参考音文本)。找不到就报清楚有哪些可选,而不是让模型去下载一个不存在的名字。"""
    wav, txt = voices_dir / f"{voice}.wav", voices_dir / f"{voice}.txt"
    if not wav.is_file() or not txt.is_file():
        have = sorted(p.stem for p in voices_dir.glob("*.wav"))
        raise ValueError(f"没有音色 {voice!r}(需要 {wav.name} 和 {txt.name});现有:{have}")
    return wav, txt.read_text(encoding="utf-8").strip()


class Qwen3Zh:
    def __init__(self, voice: str = "女声", speed: float = 1.0, instruct: str = ""):
        # speed/instruct:克隆模式跟随参考音的语速与语气,这两个参数不起作用;保留参数名是为了与启动器的设置兼容
        import numpy as np
        from faster_qwen3_tts import FasterQwen3TTS  # 惰性导入:服务器端与测试环境没有这些依赖

        self._np = np
        self.ref_audio, self.ref_text = reference(voice)
        self.model = FasterQwen3TTS.from_pretrained(BASE_REPO)

    def _say(self, seg: str):
        wavs, sr = self.model.generate_voice_clone(text=seg, language="Chinese",
                                                   ref_audio=str(self.ref_audio), ref_text=self.ref_text)
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
