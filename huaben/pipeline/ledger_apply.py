"""把"编辑·入账"的结果写进账本。整章入账在一个事务里:要么全进,要么全不进。"""
from .. import repo
from ..db import dumps, tx

_CHAR_FIELDS = ("alive", "location", "abilities", "relations", "knows", "core", "profile")
_LEDGER_WRITABLE = ("alive", "location", "abilities", "relations", "knows", "profile")


def merge_character(existing: dict | None, entry: dict) -> dict:
    """把一条入账合并进人物现状。规则(实测依据见 polish 日志第 25 节:照格式示例填满字段的入账曾清空主角状态):
    - 没给的字段沿用旧值;
    - **空值不覆盖**(空字符串、空列表):模型常把"没变化"写成空值,而不是省略;
    - `core`(每章必带)由开书时的圣经决定,入账**不能改**——否则模型照示例写一个 false 就把主角降级了。
    """
    base = {"alive": True, "location": "", "abilities": "", "relations": "", "knows": [], "core": False,
            "profile": ""}
    if existing:
        base.update({k: existing.get(k, base[k]) for k in _CHAR_FIELDS})
    base.update({k: entry[k] for k in _LEDGER_WRITABLE if k in entry and entry[k] not in ("", [])})
    return base


def revived(existing: dict | None, merged: dict) -> bool:
    """已故 → 在世。可能是有意的反转,也可能是模型照示例填了 alive=true;不拦,但要留痕供排查。"""
    return bool(existing) and not existing.get("alive", True) and merged["alive"]


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
            if revived(known.get(name), m):
                warnings.append(f"人物 {name} 由已故变为在世(若不是有意的反转,请检查入账)")
            repo.upsert_character(conn, book_id, name, updated_ch=idx, commit=False, **m)
        for f in ledger["foreshadows_new"]:
            repo.add_foreshadow(conn, book_id, idx, f["content"], f["payoff_plan"], commit=False,
                                scale=f.get("scale", "medium"))
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
        repo.update_chapter(conn, chapter_id, summary=ledger["summary"], status="accepted",
                            devices=dumps(ledger.get("devices", [])), commit=False)
    return warnings
