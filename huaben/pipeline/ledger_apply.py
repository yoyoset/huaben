"""把"编辑·入账"的结果写进账本。整章入账在一个事务里:要么全进,要么全不进。"""
from .. import repo
from ..db import tx

_CHAR_FIELDS = ("alive", "location", "abilities", "relations", "knows", "core", "profile")


def merge_character(existing: dict | None, entry: dict) -> dict:
    """模型只返回变化的字段;没返回的字段沿用旧值(否则 core 之类会被悄悄清零)。"""
    base = {"alive": True, "location": "", "abilities": "", "relations": "", "knows": [], "core": False,
            "profile": ""}
    if existing:
        base.update({k: existing.get(k, base[k]) for k in _CHAR_FIELDS})
    base.update({k: entry[k] for k in _CHAR_FIELDS if k in entry and not (k == "profile" and not entry[k])})
    return base  # 空的 profile 不覆盖已有人设(模型常把"没变化"写成空字符串)


def apply_ledger(conn, book_id: int, chapter_id: int, idx: int, ledger: dict) -> list[str]:
    """返回警告列表(例如模型引用了不存在的伏笔编号);警告不阻断入账。"""
    warnings: list[str] = []
    known = {c["name"]: c for c in repo.list_characters(conn, book_id)}
    # 伏笔状态只能前进(planted → progressing → resolved);已回收的不能被改回去,否则回收记录丢失
    status_of = {f["id"]: f["status"] for f in repo.list_foreshadows(conn, book_id)}
    with tx(conn):
        for entry in ledger["characters"]:
            name = entry["name"]  # 已由 normalize 规整:去空白、非空
            m = merge_character(known.get(name), entry)
            repo.upsert_character(conn, book_id, name, updated_ch=idx, commit=False, **m)
        for f in ledger["foreshadows_new"]:
            repo.add_foreshadow(conn, book_id, idx, f["content"], f["payoff_plan"], commit=False)
        for u in ledger["foreshadows_update"]:
            fid, status = u["id"], u["status"]
            if fid not in status_of:
                warnings.append(f"foreshadow #{fid} not found, skipped")
                continue
            if status_of[fid] == "resolved":
                warnings.append(f"foreshadow #{fid} already resolved, update to {status!r} ignored")
                continue
            repo.update_foreshadow(conn, fid, status=status,
                                   resolved_ch=idx if status == "resolved" else None, commit=False)
        for fact in ledger["facts"]:
            repo.add_fact(conn, book_id, fact, idx, commit=False)
        repo.update_chapter(conn, chapter_id, summary=ledger["summary"], status="accepted", commit=False)
    return warnings
