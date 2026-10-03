"""引擎:Qwen3-TTS 1.7B(阿里通义,Apache-2.0),经 faster-qwen3-tts(MIT)用 CUDA graph 加速;**克隆一段固定参考音**。

为什么换(2026-10-02 用户):Kokoro 的音色不行,3060 应该跑得动更好的。
速度(RTX 3060 12GB,Windows):官方 qwen-tts 0.12 倍实时,每步解码约 500 次小 kernel 启动、Windows 上启动开销压倒计算
(不是显存问题,释放显存后实测一样);faster-qwen3-tts 1.8 倍实时,一章 10 分钟音频约 5~6 分钟。

为什么是"克隆参考音"而不是内置音色/一句话设计音色(2026-10-03 用户试听:音色前后不一致,对白被读成评书腔):
一章要切成几十段分别合成,内置音色和设计音色每一段都是模型现场"想"出来的声音,段与段之间会漂。
2026-10-03 改为跨段落合并,见 `chunks.py`。实测同一段 4 段正文,
每段音高中位数:Serena 内置 241/269/204/251 Hz(极差 66),设计的评书男声 87/260/157/180 Hz(极差 173,像换了人);
改成每段都克隆同一段 10 秒参考音后:女 236~277(41)、男 174~208(34)。
参考音放在 pc_worker/voices/<名字>.wav,旁边的 <名字>.txt 是参考音里说的话(克隆要用)。

依赖装在单独的 .venv-qwen:要 transformers 5.15.x,与 Kokoro 用的 4.x 冲突。见 requirements-qwen.txt。
"""
import logging
from pathlib import Path

from .chunks import chunks
from .kokoro_zh import encode_mp3  # 切块与编码两个引擎通用

log = logging.getLogger("huaben_voice")
BASE_REPO = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
VOICES_DIR = Path(__file__).resolve().parent.parent / "voices"
MAX_SEG_CHARS = 200          # 太长的一次生成容易语气漂移、偶发吞字;块长的实测见 T002
CHUNK_PAUSE_S = 0.35         # 块与块之间的停顿;块内的停顿由模型按标点自己处理

# 防"停不下来":2026-10-03 正式配音第一章,一段不到 200 字的正文生成了 161 秒音频(正常 40 秒左右)——
# 模型没有收尾、一直生成到默认上限 2048 个 token(12 token/秒 ≈ 170 秒),这一段就是长时间的乱音/重复。
CHARS_PER_S = 5.0            # 实测克隆音色语速:约 350 字 → 64~68 秒
RUNAWAY_FACTOR = 2.5         # 超过预计时长 2.5 倍算失控
TOKENS_PER_S = 12            # 模型名里的 12Hz:编解码器每秒 12 个 token
RETRIES = 2


def expected_s(text: str) -> float:
    return max(len(text) / CHARS_PER_S, 1.0)


def token_cap(text: str) -> int:
    """这一段最多允许生成多少 token:预计时长的 RUNAWAY_FACTOR 倍,至少 6 秒。纯函数。"""
    return int(max(expected_s(text) * RUNAWAY_FACTOR, 6.0) * TOKENS_PER_S)


def runaway(text: str, seconds: float) -> bool:
    return seconds > expected_s(text) * RUNAWAY_FACTOR * 0.95  # 顶到上限附近也算:那多半是被截断的失控


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

    def _once(self, seg: str):
        wavs, sr = self.model.generate_voice_clone(text=seg, language="Chinese", ref_audio=str(self.ref_audio),
                                                   ref_text=self.ref_text, max_new_tokens=token_cap(seg))
        return self._np.concatenate([self._np.asarray(w, dtype="float32").reshape(-1) for w in wavs]), sr

    def _say(self, seg: str):
        """失控就重来(采样有随机性,重来通常就正常了),最多 RETRIES 次,留最短的一次。"""
        best = None
        for _ in range(RETRIES + 1):
            audio, sr = self._once(seg)
            if best is None or len(audio) < len(best[0]):
                best = (audio, sr)
            if not runaway(seg, len(audio) / sr):
                break
            log.warning("这一段生成失控(%.0f 秒,预计 %.0f 秒),重来:%s…", len(audio) / sr, expected_s(seg), seg[:20])
        return best

    def synthesize(self, text: str) -> bytes:
        np, pieces, sr = self._np, [], 24000
        for block in chunks(text, MAX_SEG_CHARS):
            audio, sr = self._say(block)
            pieces.append(audio)
            pieces.append(np.zeros(int(sr * CHUNK_PAUSE_S), dtype="float32"))
        if not pieces:
            raise ValueError("没有可朗读的文本")
        return encode_mp3(np.concatenate(pieces), sr)
