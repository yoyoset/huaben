"""章节音频文件:路径、原子落盘、播哪一份。

一章最多两份音频:basic(edge-tts,服务器上合成)与 hq(电脑上的本地中文模型合成,2026-10-02 起为主路径)。
两份都留着(用户偏好:新旧并行保留),播放时**优先 hq**;某份文件丢了就退到另一份,而不是 404。
"""
import hashlib
import os

from ..config import Settings

PREFERENCE = ("hq", "basic")  # 播放优先顺序


def audio_relpath(book_id: int, idx: int, quality: str = "basic", voice: str = "") -> str:
    # basic 沿用最初的文件名,升级前已有的音频不用搬。
    # 带音色的电脑版:文件名里带音色的短哈希——换音色重配后地址跟着变,浏览器不会接着播缓存里的旧音色
    if quality == "basic":
        return f"{book_id}/{idx:04d}.mp3"
    tag = f".{hashlib.sha1(voice.encode()).hexdigest()[:8]}" if voice else ""
    return f"{book_id}/{idx:04d}.{quality}{tag}.mp3"


def audio_file_ok(settings: Settings, relpath: str | None) -> bool:
    """"可以播"以文件为准:数据库有记录但文件不在(例如只恢复了数据库备份)不算。"""
    return bool(relpath) and (settings.audio_dir / relpath).is_file()


def best_playable(settings: Settings, paths: dict[str, str | None]) -> str | None:
    """paths:quality → 登记的相对路径。按 PREFERENCE 返回第一份文件确实存在的。"""
    for q in PREFERENCE:
        if audio_file_ok(settings, paths.get(q)):
            return paths[q]
    return None


def index_paths(row: dict) -> dict[str, str | None]:
    """repo.chapter_index 的一行 → {质量: 登记路径}。"""
    return {"hq": row.get("hq_path"), "basic": row.get("audio_path")}


def write_audio(settings: Settings, relpath: str, data: bytes) -> None:
    dest = settings.audio_dir / relpath
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, dest)  # 原子:播放器永远看不到写了一半的文件


def remove_audio(settings: Settings, relpath: str | None) -> None:
    """换音色重配后删掉被替换的旧文件:音频可以由正文随时重新合成(也不在备份范围内),留着只占盘。"""
    if relpath:
        (settings.audio_dir / relpath).unlink(missing_ok=True)
