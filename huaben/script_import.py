"""剧本制导入:把架构方写好的 book.json 与卷剧本写进库。

故事的全部决定由架构方写成 stories/<书名>/,不再经过"开书对话 → 模型定稿"。
书目导入见 T010(import_book);卷与章纲见 T011(import_volume)。
真相层 secrets 只存不用:不进任何模型提示词,也不进任何读者接口。
"""
import json

from . import repo
from .arc import normalize_arc
from .craft import normalize_craft
from .db import tx
from .opening.parsing import parse_bible
from .opening.save_bible import save_parsed_bible
from .pipeline.volume import seal_volume


class ScriptImportError(Exception):
    def __init__(self, message: str, problems: list[str] | None = None):
        super().__init__(message)
        self.problems = problems if problems is not None else [message]


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


def resolve_keys(outline: dict, ids_by_key: dict[str, int]) -> tuple[dict, list[str]]:
    """章纲里 foreshadows 的代号 → 数据库编号。返回(新章纲, 翻译不了的代号)。已经是整数的原样保留。"""
    ids, missing = [], []
    for k in outline.get("foreshadows") or []:
        if isinstance(k, int):
            ids.append(k)
        elif k in ids_by_key:
            ids.append(ids_by_key[k])
        else:
            missing.append(str(k))
    return {**outline, "foreshadows": ids}, missing


def check_volume_script(data: dict, known_keys: set[str], room: int | None = None) -> list[str]:
    """剧本的硬性检查,返回问题列表(空 = 合格)。known_keys:这本书此前已经埋下(或已在剧本里排好要埋)的伏笔代号。
    data 带 "volume" = 开新卷(本卷可容纳的章数 = beat_chapters 之和);不带 = 给进行中的卷续一批章纲,
    此时 room 由调用方给:本卷还能再放几章。一卷的章纲可以分几批导入,所以章数只要求"不超过",不要求"正好"。"""
    problems = []
    chapters = data.get("chapters") or []
    if "volume" in data:
        vol = data.get("volume") or {}
        beats, budget = vol.get("beats") or [], vol.get("beat_chapters") or []
        if not str(vol.get("goal") or "").strip():
            problems.append("volume.goal 为空")
        if not beats or len(budget) != len(beats) or any(not isinstance(n, int) or n < 1 for n in budget):
            problems.append("beat_chapters 必须与 beats 等长,且每项是 ≥1 的整数")
        else:
            room = sum(budget)
    if not chapters:
        problems.append("没有章纲")
    elif room is not None and len(chapters) > room:
        problems.append(f"章纲有 {len(chapters)} 章,但本卷只能再放 {room} 章")
    keys = set(known_keys)
    for n, ch in enumerate(chapters, 1):
        for field in ("title", "outline", "when", "payoff", "hook"):
            if not str(ch.get(field) or "").strip():
                problems.append(f"第 {n} 章缺 {field}")
        for k in ch.get("foreshadows") or []:
            if k not in keys:
                problems.append(f"第 {n} 章引用了还没埋下的伏笔代号 {k!r}")
        plant = ch.get("plant")
        if plant:
            k = str(plant.get("key") or "").strip()
            if not k or not str(plant.get("content") or "").strip() or not str(plant.get("truth") or "").strip():
                problems.append(f"第 {n} 章的 plant 缺 key / content / truth")
            elif k in keys:
                problems.append(f"第 {n} 章的伏笔代号 {k!r} 重复")
            keys.add(k)
    titles = [str(ch.get("title") or "").strip() for ch in chapters]
    problems += [f"章节标题重复:{t}" for t in sorted({t for t in titles if t and titles.count(t) > 1})]
    return problems


def _known_keys(conn, book_id: int) -> set[str]:
    keys = set(repo.foreshadow_ids_by_key(conn, book_id))
    for o in repo.list_scripted_outlines(conn, book_id):
        k = str(((o.get("plant") or {}).get("key")) or "").strip()
        if k:
            keys.add(k)
    return keys


def _room(conn, book_id: int, vol: dict) -> int:
    """本卷还能再放几章 = 计划章数 − 本卷已有剧本章纲的章数(已写 + 未写)。"""
    pending = repo.max_scripted_idx(conn, book_id) - repo.count_accepted(conn, book_id)
    imported = repo.count_accepted(conn, book_id, vol["id"]) + pending
    return vol["target_chapters"] - imported


def _save(conn, book_id: int, outlines: dict) -> None:
    with tx(conn):
        repo.save_scripted_outlines(conn, book_id, outlines, commit=False)
        repo.update_book(conn, book_id, gen_error="", commit=False)


def import_volume(conn, llm, settings, book_id: int, data: dict) -> dict:
    """导入一卷剧本或多批章纲。带 "volume" 开新卷(写满先封卷),不带则给进行中的卷续章纲。"""
    book = repo.get_book(conn, book_id)
    if not book or not book.get("scripted"):
        raise ScriptImportError("不是剧本书:这本书的章纲来自模型,不能用卷剧本导入")
    vol = repo.active_volume(conn, book_id)
    if "volume" in data:
        if vol is not None:
            if repo.count_accepted(conn, book_id, vol["id"]) < vol["target_chapters"]:
                raise ScriptImportError("当前这一卷还没写完,续章纲请去掉 volume")
            seal_volume(conn, llm, settings, book_id, vol)  # 照 ensure_active_volume:写满先封卷
            vol = None
        room = None
    else:
        if vol is None:
            raise ScriptImportError("没有进行中的卷,开新卷请带上 volume")
        room = _room(conn, book_id, vol)
    problems = check_volume_script(data, _known_keys(conn, book_id), room)
    if problems:
        raise ScriptImportError("; ".join(problems), problems)
    chapters = data["chapters"]
    max_idx = repo.max_scripted_idx(conn, book_id)
    start = max_idx + 1 if max_idx else repo.next_chapter_idx(conn, book_id)
    outlines = {start + i: ch for i, ch in enumerate(chapters)}
    if "volume" not in data:
        _save(conn, book_id, outlines)
        return {"volume_idx": vol["idx"], "chapters": [start, start + len(chapters) - 1]}
    v = data["volume"]
    budget = [int(n) for n in v["beat_chapters"]]
    ids_by_key = repo.foreshadow_ids_by_key(conn, book_id)
    resolve = []
    for k in v.get("resolve") or []:
        if k not in ids_by_key:
            raise ScriptImportError(f"resolve 里的伏笔代号 {k!r} 还没埋下,无法翻译成编号")
        resolve.append(ids_by_key[k])
    idx = len(repo.list_volumes(conn, book_id)) + 1
    with tx(conn):
        repo.create_volume(conn, book_id, idx, goal=str(v.get("goal") or ""), beats=v.get("beats") or [],
                           plant=v.get("plant") or [], resolve=resolve, status="active", target_chapters=sum(budget),
                           arc=normalize_arc(v.get("arc"), len(v.get("beats") or [])), beat_chapters=budget,
                           commit=False)
        repo.save_scripted_outlines(conn, book_id, outlines, commit=False)
        repo.update_book(conn, book_id, gen_error="", commit=False)
    return {"volume_idx": idx, "chapters": [start, start + len(chapters) - 1]}
