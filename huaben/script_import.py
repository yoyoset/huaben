"""剧本制导入(T010):把架构方写好的 book.json 变成一本可以连载的书。

故事的全部决定(世界、人物、真相层、文风)由架构方写成 stories/<书名>/book.json,不再经过"开书对话 → 模型定稿"。
本文件只做书目导入;卷与章纲见 T011。真相层 secrets 只存不用:不进任何模型提示词,也不进任何读者接口。
"""
import json

from . import repo
from .craft import normalize_craft
from .opening.parsing import parse_bible
from .opening.save_bible import save_parsed_bible


class ScriptImportError(Exception):
    pass


def import_book(conn, data: dict) -> int:
    """book.json → 一本 status='serializing'、scripted=1 的书,返回 book_id。
    此时还没有卷:要再导入卷剧本(T011)才会开始写。出错不留半本书。"""
    name = str(data.get("profile") or "").strip()
    profiles = repo.list_profiles(conn)
    profile = next((p for p in profiles if p["name"] == name), None)
    if profile is None:
        have = "、".join(p["name"] for p in profiles) or "(还没有读者)"
        raise ScriptImportError(f"找不到读者 {name!r};现有:{have}")
    bible = parse_bible(json.dumps(data.get("bible") or {}, ensure_ascii=False))  # 校验不合格原样抛 ParseError
    if any(b["title"] == bible["title"] for b in repo.list_books(conn, profile["id"])):
        raise ScriptImportError(f"这位读者名下已有同名的书:{bible['title']}")
    craft = normalize_craft(data.get("craft"))
    book_id = repo.create_book(conn, bible["title"], genre=str(bible.get("genre") or ""), profile_id=profile["id"])
    try:
        save_parsed_bible(conn, book_id, bible, [str(s) for s in data.get("style_samples") or []],
                          secrets=str(data.get("secrets") or ""))
        repo.update_book(conn, book_id, status="serializing", scripted=1,
                         craft=json.dumps(craft, ensure_ascii=False), gen_error="")
    except Exception:
        repo.delete_book(conn, book_id)
        raise
    return book_id
