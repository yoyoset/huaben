"""引擎:Kokoro-82M-v1.1-zh(hexgrad 的中文专用版,不是爱读用的英文版)。

选它"先跑通"的理由(2026-10-02):Windows 上 pip 装得干净、模型约 330MB、3060 上很快;爱读已证明 Kokoro 这套栈
在这块显卡上能跑。表现力更强的 CosyVoice2 / IndexTTS2 在 Windows 上安装问题多,放到"使用中优化质量"阶段再比,
接口相同,换引擎不动别处。

依赖与模型:见 pc_worker/requirements-kokoro.txt;模型首次运行时从 HuggingFace 下载并缓存。
"""
import io
import re

REPO_ID = "hexgrad/Kokoro-82M-v1.1-zh"
SAMPLE_RATE = 24000
MAX_SEG_CHARS = 120        # 单段过长会超出模型的音素上限被截断(Kokoro 约 510 个音素),按句切小
PARAGRAPH_PAUSE_S = 0.45   # 段与段之间的停顿;句与句之间的停顿由模型按标点自己处理

# 全角标点用 \u 转义写:源码编辑时全角符号曾被悄悄换成半角(见 huaben/pipeline/draft_check.py)
_SENT_END = re.compile("(?<=[!?;。！？…；])")


def segments(text: str, max_chars: int = MAX_SEG_CHARS) -> list[list[str]]:
    """按段落切,段内按句末标点把句子拼成 ≤ max_chars 的小段;超长单句硬切。不丢字。纯函数。"""
    out = []
    for para in (p.strip() for p in text.split("\n")):
        if not para:
            continue
        segs, cur = [], ""
        for sent in (s for s in _SENT_END.split(para) if s):
            while len(sent) > max_chars:
                if cur:
                    segs.append(cur)
                    cur = ""
                segs.append(sent[:max_chars])
                sent = sent[max_chars:]
            if cur and len(cur) + len(sent) > max_chars:
                segs.append(cur)
                cur = ""
            cur += sent
        if cur:
            segs.append(cur)
        out.append(segs)
    return out


class KokoroZh:
    def __init__(self, voice: str = "zf_001", speed: float = 1.0, device: str | None = None):
        import torch  # 惰性导入:服务器端与测试环境不需要 torch
        from kokoro import KModel, KPipeline

        self.voice, self.speed = voice, speed
        device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._np = __import__("numpy")
        self.model = KModel(repo_id=REPO_ID).to(device).eval()
        # 中文里夹的英文词交给英文管线出音素(模型卡的推荐用法)
        en = KPipeline(lang_code="a", repo_id=REPO_ID, model=False)
        self.pipe = KPipeline(lang_code="z", repo_id=REPO_ID, model=self.model,
                              en_callable=lambda t: next(en(t)).phonemes)
        self.device = device

    def _say(self, seg: str):
        parts = [r.audio.cpu().numpy() if hasattr(r.audio, "cpu") else r.audio
                 for r in self.pipe(seg, voice=self.voice, speed=self.speed) if r.audio is not None]
        return self._np.concatenate(parts) if parts else self._np.zeros(0, dtype="float32")

    def synthesize(self, text: str) -> bytes:
        np = self._np
        pause = np.zeros(int(SAMPLE_RATE * PARAGRAPH_PAUSE_S), dtype="float32")
        chunks = []
        for para in segments(text):
            chunks += [self._say(s) for s in para] + [pause]
        if not chunks:
            raise ValueError("没有可朗读的文本")
        return encode_mp3(np.concatenate(chunks), SAMPLE_RATE)


def encode_mp3(samples, sample_rate: int) -> bytes:
    """soundfile(libsndfile ≥ 1.1)直接写 MP3;2026-10-02 在本机实测可用。"""
    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="MP3")
    return buf.getvalue()
