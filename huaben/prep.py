"""出门前"预备 N 章"(2026-10-03 用户:出去跑步前下好、离线听,支持预跑 10 章、20 章)。纯函数。

平时后台只比读者进度多写 buffer_chapters 章(默认 3);预备时把"要写到哪一章"临时提到 当前章 + N - 1,
写好后电脑配音程序按听的先后顺序配(voice_queue 已经从当前章往后排),手机 App 再把这些章的 MP3 下到本地。
"""
MAX_PREP = 50


def prep_range(last_opened: int, n: int) -> tuple[int, int]:
    """从正在读/听的那章起,连续 n 章(含当前章:出门时多半是接着这章往下听)。"""
    start = max(1, last_opened)
    return start, start + max(1, min(n, MAX_PREP)) - 1


def buffer_target(default: int, read_pos: int, prep_until: int) -> int:
    """后台要保持"读到的最远章之后已写好几章"。预备的章还没写完时临时调高,写完/读过之后自然回落到默认。"""
    return max(default, prep_until - read_pos)


def prep_view(start: int, end: int, chapters: list[dict]) -> dict:
    """chapters:范围内已写好的章 [{idx, title, has_audio, audio_url}]。给页面/App 显示进度、给 App 列出要下的文件。"""
    total = end - start + 1
    return {"start": start, "end": end, "total": total,
            "text_ready": len(chapters), "audio_ready": sum(1 for c in chapters if c["has_audio"]),
            "done": len(chapters) == total and all(c["has_audio"] for c in chapters),
            "chapters": chapters}


def book_buffer_target(book: dict, default: int) -> int:
    return buffer_target(default, book["read_pos"], book.get("prep_until") or 0)
