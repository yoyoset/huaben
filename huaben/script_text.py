"""剧本制:导入架构方写好的正文(T016)。

有导入正文的章,用导入的(只记账,不让写作模型重写);没有的章照旧由模型按章纲写,两种可混用。
记账(摘要、人物、伏笔、事实)照旧由写作模型做,后面的章靠这些接上。
"""
from . import repo
from .pipeline.draft_check import clean_draft
from .script_import import ScriptImportError

MIN_IMPORTED_CHARS = 500  # 导入的正文清洗后至少这么多字


def import_chapter_texts(conn, book_id: int, chapters: list[dict]) -> dict:
    """[{"idx": 章号, "body": 正文}] → 存进 scripted_bodies。返回 {"saved": [章号…]}。
    硬检查:任何一条不过就整批不存,把所有问题一起报出来。"""
    book = repo.get_book(conn, book_id)
    problems = []
    if not book or not book.get("scripted"):
        problems.append("不是剧本书:不能导入正文")
    seen, clean = set(), {}
    for item in chapters or []:
        idx = item.get("idx") if isinstance(item, dict) else None
        if isinstance(idx, bool) or not isinstance(idx, int):
            problems.append(f"正文的章号必须是整数,得到 {idx!r}")
            continue
        if idx in seen:
            problems.append(f"章号重复:{idx}")
            continue
        seen.add(idx)
        if repo.get_scripted_outline(conn, book_id, idx) is None:
            problems.append(f"第{idx}章还没有剧本章纲,正文要对着章纲记账")
            continue
        existing = repo.get_chapter(conn, book_id, idx)
        if existing is not None and existing["status"] == "accepted":
            problems.append(f"第{idx}章已经定稿,不能靠导入改写")
            continue
        body = clean_draft(str(item.get("body") or ""))
        if len(body) < MIN_IMPORTED_CHARS:
            problems.append(f"第{idx}章正文清洗后只有 {len(body)} 字,不到 {MIN_IMPORTED_CHARS} 字")
            continue
        clean[idx] = body
    if problems:
        raise ScriptImportError("; ".join(problems), problems)
    repo.save_scripted_bodies(conn, book_id, clean)
    return {"saved": [item["idx"] for item in chapters]}
