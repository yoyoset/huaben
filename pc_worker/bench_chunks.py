"""在显卡上实测"一块多长最稳":三种切法各配一遍,比失控次数与音高/语速一致性。

为什么(任务卡 T002):T001 先把块长定在约 200 字。用户希望一次生成得越长越好(声音越连贯),
但越长越容易失控/漂移,到底 200 / 400 / 更长不猜,测。本脚本只出数字,不选默认值——最终由架构方和用户定。

用法(要用显卡,先关掉『话本配音』):
    pc_worker/.venv-qwen/Scripts/python.exe pc_worker/bench_chunks.py samples/voice_bench/chapter.txt
"""
import statistics
import sys
import time
from pathlib import Path

import librosa
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from huaben_voice.chunks import chunks  # noqa: E402
from huaben_voice.kokoro_zh import encode_mp3, segments  # noqa: E402
from huaben_voice.qwen3_zh import Qwen3Zh, runaway  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "samples" / "voice_bench"
SAMPLE_RATE = 24000
CLIP_S = 120


def cut(text: str, name: str) -> list[str]:
    if name == "old":
        return [s for p in segments(text, 200) for s in p]
    if name == "c200":
        return chunks(text, 200, 300)
    return chunks(text, 400, 500)


def pitch_hz(audio, sr) -> float | None:
    """有声帧的音高中位数(Hz);不到 1 秒的块太短测不准,返回 None 跳过。"""
    y = np.asarray(audio, dtype="float32")
    if len(y) / sr < 1.0:
        return None
    f0, _, _ = librosa.pyin(y, fmin=60, fmax=500, sr=sr)
    vals = f0[np.isfinite(f0)]
    return float(np.median(vals)) if vals.size else None


def run(engine, text: str, name: str) -> str:
    segs = cut(text, name)
    pieces, pitches, rates, runaway_n, skipped, elapsed = [], [], [], 0, 0, 0.0
    for seg in segs:
        t0 = time.perf_counter()
        audio, sr = engine._once(seg)   # 不走重试,才能数出失控次数
        elapsed += time.perf_counter() - t0
        seconds = len(audio) / sr
        if runaway(seg, seconds):
            runaway_n += 1
        pieces.append(audio)
        hz = pitch_hz(audio, sr)
        if hz is None:
            skipped += 1
        else:
            pitches.append(hz)
        rates.append(len(seg) / seconds if seconds else 0.0)
    audio_s = sum(len(a) for a in pieces) / SAMPLE_RATE
    line = (f"{name}: 块数 {len(segs)}, 失控 {runaway_n}, 音频 {audio_s:.1f}s, 耗时 {elapsed:.1f}s, "
            f"音高 min {min(pitches):.0f} max {max(pitches):.0f} 极差 {max(pitches) - min(pitches):.0f} "
            f"标准差 {statistics.pstdev(pitches):.0f}, 跳过 {skipped} 块, "
            f"语速 min {min(rates):.2f} max {max(rates):.2f} 标准差 {statistics.pstdev(rates):.2f} 字/秒")
    clip, acc = [], 0.0
    for a in pieces:
        clip.append(a)
        acc += len(a) / SAMPLE_RATE
        if acc >= CLIP_S:
            break
    (OUT / f"{name}.mp3").write_bytes(encode_mp3(np.concatenate(clip), SAMPLE_RATE))
    return line


def main() -> None:
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    engine = Qwen3Zh(voice="女声")
    lines = []
    for name in ("old", "c200", "c400"):
        try:
            line = run(engine, text, name)
        except Exception as e:  # 超过 2048 token 被模型拒绝时,只这一行标注,其它两行照常
            line = f"{name}: 模型拒绝 {type(e).__name__}: {e}"
        print(line, flush=True)
        lines.append(line)
    (OUT / "result.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
