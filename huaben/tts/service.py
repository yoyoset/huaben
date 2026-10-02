"""章节配音编排:清洗 → 切块 → 逐块合成(带重试、校验 MP3)→ 拼接 → 原子落盘 → 登记。

MP3 是帧流,字节拼接即可连续播放,所以分块合成后直接拼。
"""
import os
import time
from pathlib import Path

from .. import repo
from ..config import Settings
from .base import TTS, TTSError
from .mp3 import is_mp3
from .text import clean_for_tts, split_for_tts


def audio_relpath(book_id: int, idx: int) -> str:
    return f"{book_id}/{idx:04d}.mp3"


def synthesize_text(tts: TTS, text: str, settings: Settings, sleep=time.sleep) -> bytes:
    chunks = split_for_tts(clean_for_tts(text), settings.tts_chunk_chars)
    if not chunks:
        raise TTSError("没有可朗读的文本")
    parts: list[bytes] = []
    for chunk in chunks:
        for attempt in range(settings.tts_retries + 1):
            try:
                data = tts.synthesize(chunk)
                if not is_mp3(data):  # 不是 MP3 就是服务端/库的格式变了,重试没用,显式失败
                    raise TTSError("合成产物不是 MP3(可能是 WebM/Opus)")
                parts.append(data)
                break
            except TTSError as e:
                if "不是 MP3" in str(e) or attempt == settings.tts_retries:
                    raise
                sleep(2 ** attempt)
    return b"".join(parts)


def ensure_chapter_audio(conn, tts: TTS, settings: Settings, chapter: dict, sleep=time.sleep) -> Path:
    """为一章生成保底音频;已有则直接返回。失败抛 TTSError 并记 pipeline_runs。"""
    existing = repo.get_audio(conn, chapter["id"])
    rel = audio_relpath(chapter["book_id"], chapter["idx"])
    dest = settings.audio_dir / rel
    if existing and dest.exists():
        return dest
    spoken = f"第{chapter['idx']}章,{chapter['title']}。\n{chapter['body']}" if chapter["title"] else chapter["body"]
    t0 = time.monotonic()
    try:
        data = synthesize_text(tts, spoken, settings, sleep)
    except TTSError as e:
        repo.log_run(conn, chapter["book_id"], "tts", chapter_idx=chapter["idx"], ok=False, note=str(e)[:300],
                     duration_ms=int((time.monotonic() - t0) * 1000))
        raise
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".mp3.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, dest)  # 原子:播放器永远看不到写了一半的文件
    repo.set_audio(conn, chapter["id"], "basic", rel)
    repo.log_run(conn, chapter["book_id"], "tts", chapter_idx=chapter["idx"],
                 duration_ms=int((time.monotonic() - t0) * 1000), note=f"{len(data)} bytes")
    return dest


def fill_audio(conn, tts: TTS, settings: Settings, book_id: int, sleep=time.sleep) -> tuple[int, str]:
    """给所有缺音频的已定稿章配音(也补历史空缺)。遇到失败就停,返回 (已完成章数, 错误摘要)。"""
    done = 0
    for ch in repo.chapters_missing_audio(conn, book_id):
        try:
            ensure_chapter_audio(conn, tts, settings, ch, sleep)
        except TTSError as e:
            # 技术细节已由 ensure_chapter_audio 记进 pipeline_runs;这里返回给界面的人话
            return done, f"第 {ch['idx']} 章配音失败,文字可以照常阅读;稍后会自动重试。"
        done += 1
    return done, ""
