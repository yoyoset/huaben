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


def audio_file_ok(settings: Settings, relpath: str | None) -> bool:
    """"可以播"以文件为准:数据库有记录但文件不在(例如只恢复了数据库备份)不算。"""
    return bool(relpath) and (settings.audio_dir / relpath).is_file()


def chapters_needing_audio(conn, settings: Settings, book_id: int) -> list[dict]:
    """没登记音频的章 + 登记了但文件已丢失的章(先后顺序由 listening_order 决定)。"""
    lost = [c for c in repo.voiced_chapters(conn, book_id) if not audio_file_ok(settings, c["audio_path"])]
    return repo.chapters_missing_audio(conn, book_id) + lost


def listening_order(chapters: list[dict], pos: int) -> list[dict]:
    """配音的先后:先配读者接下来要听的(从当前章往后),再往回补已经听过的(越近越先,重听的多半是最近几章)。"""
    ahead = sorted((c for c in chapters if c["idx"] >= pos), key=lambda c: c["idx"])
    behind = sorted((c for c in chapters if c["idx"] < pos), key=lambda c: -c["idx"])
    return ahead + behind


def audio_round_limit(settings: Settings) -> int:
    """一轮最多配几章。正常连载时一轮新增的章不超过缓冲章数,再加上正在听的这一章——所以平时碰不到上限;
    只有恢复备份后大批重配时才分轮进行:每轮都放锁,文字补货和别的书(后台只有一个线程)不会被拖住几十分钟。"""
    return settings.buffer_chapters + 1


def fill_audio(conn, tts: TTS, settings: Settings, book_id: int, sleep=time.sleep, *,
               pos: int = 1, limit: int | None = None) -> tuple[int, str]:
    """按 listening_order 给缺音频(含文件丢失)的已定稿章配音,最多 limit 章(None = 不限);剩下的留给下一轮。
    遇到失败就停,返回 (已完成章数, 错误摘要)。"""
    done = 0
    for ch in listening_order(chapters_needing_audio(conn, settings, book_id), pos)[:limit]:
        try:
            ensure_chapter_audio(conn, tts, settings, ch, sleep)
        except TTSError as e:
            # 技术细节已由 ensure_chapter_audio 记进 pipeline_runs;这里返回给界面的人话
            return done, f"第 {ch['idx']} 章配音失败,文字可以照常阅读;稍后会自动重试。"
        done += 1
    return done, ""
