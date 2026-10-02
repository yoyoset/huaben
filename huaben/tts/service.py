"""章节配音编排:清洗 → 切块 → 逐块合成(带重试、校验 MP3)→ 拼接 → 原子落盘 → 登记。

MP3 是帧流,字节拼接即可连续播放,所以分块合成后直接拼。
"""
import time
from pathlib import Path

from .. import repo
from ..config import Settings
from .base import TTS, TTSError
from .mp3 import is_mp3
from .store import PREFERENCE, audio_file_ok, audio_relpath, best_playable, write_audio  # noqa: F401
from .text import clean_for_tts, split_for_tts


def spoken_text(chapter: dict) -> str:
    """朗读的文本:章名 + 正文。电脑上的配音程序拿到的也是这一份,两种音色念的内容一致。"""
    return f"第{chapter['idx']}章,{chapter['title']}。\n{chapter['body']}" if chapter["title"] else chapter["body"]


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
    t0 = time.monotonic()
    try:
        data = synthesize_text(tts, spoken_text(chapter), settings, sleep)
    except TTSError as e:
        repo.log_run(conn, chapter["book_id"], "tts", chapter_idx=chapter["idx"], ok=False, note=str(e)[:300],
                     duration_ms=int((time.monotonic() - t0) * 1000))
        raise
    write_audio(settings, rel, data)
    repo.set_audio(conn, chapter["id"], "basic", rel)
    repo.log_run(conn, chapter["book_id"], "tts", chapter_idx=chapter["idx"],
                 duration_ms=int((time.monotonic() - t0) * 1000), note=f"{len(data)} bytes")
    return dest


def chapter_audio(conn, settings: Settings, chapter_id: int) -> str | None:
    """这一章现在能播的音频(相对路径):优先电脑版 hq,没有或文件丢了退到 edge 版;都没有返回 None。"""
    paths = {q: (rec or {}).get("path") for q in PREFERENCE for rec in [repo.get_audio(conn, chapter_id, q)]}
    return best_playable(settings, paths)


def voice_fallback(conn, tts: TTS, settings: Settings, book_id: int, pos: int = 1,
                   sleep=time.sleep) -> tuple[int, str]:
    """电脑没开时,用户手动选"先用 edge-tts 配":只配**现在一份能播的音频都没有**的章(已有电脑版的不重复配)。
    电脑版之后照样会来升级——edge 版只是先顶着。遇到失败就停,返回 (已完成章数, 人话错误)。"""
    todo = [c for c in chapters_needing_audio(conn, settings, book_id) if chapter_audio(conn, settings, c["id"]) is None]
    done = 0
    for ch in listening_order(todo, pos):
        try:
            ensure_chapter_audio(conn, tts, settings, ch, sleep)
        except TTSError:
            return done, f"第 {ch['idx']} 章用 edge-tts 配音失败,文字可以照常阅读;可以稍后再试,或等电脑开机。"
        done += 1
    return done, ""


def chapters_needing_audio(conn, settings: Settings, book_id: int, quality: str = "basic") -> list[dict]:
    """没登记该质量音频的章 + 登记了但文件已丢失的章(先后顺序由 listening_order 决定)。"""
    lost = [c for c in repo.voiced_chapters(conn, book_id, quality) if not audio_file_ok(settings, c["audio_path"])]
    return repo.chapters_missing_audio(conn, book_id, quality) + lost


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
