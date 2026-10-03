"""出门前"预备 N 章"(2026-10-03 用户:出去跑步前下好、离线听,支持预跑 10 章、20 章)。纯函数。

平时后台只比读者进度多写 buffer_chapters 章(默认 3);预备时把"要写到哪一章"临时提到 已写好的最后一章 + N,
写好后电脑配音程序按听的先后顺序配(voice_queue 已经从当前章往后排),手机 App 再把这些章的 MP3 下到本地。
2026-10-04 用户实测:写好 4 章、读到第 1 章,点"备 10 章"得到第 1~10 章(只多 6 章),与"再往后多备 N 章"的
预期不符——N 指**在已写好的基础上再往后多备 N 章**,已写好的不算在 N 里。
"""
MAX_PREP = 50


def prep_range(last_opened: int, written: int, n: int) -> tuple[int, int]:
    """起点 = 正在读/听的那章;终点 = 已写好的最后一章再往后 n 章(n 一次最多 MAX_PREP)。
    written:已写好的章数(章号连续,从 1 起)。读者停在比已写好更靠后的地方(不该出现)时,从他停的那章往后数。"""
    start = max(1, last_opened)
    return start, max(written, start - 1) + max(1, min(n, MAX_PREP))


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
