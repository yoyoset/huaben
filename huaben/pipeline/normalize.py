"""把编辑步骤的 JSON 规整成下游可以放心使用的形状。纯函数。

原则:**常见的无害变形就地规整**(字符串当成单元素、"否"当成 false、数字串当成编号),
**真正无法理解的内容抛 ParseError**(由流水线当作一次失败的尝试)。
下游(入账、prompt 组装)因此只会见到确定类型,不会在半路抛 TypeError/ValueError 变成静默失败。
"""
from ..devices import normalize_devices
from ..foreshadow_scale import normalize_scale
from ..signature import normalize_signature
from .jsonout import ParseError

_TRUE = {"true", "yes", "y", "1", "是", "存活", "活", "活着", "对"}
_FALSE = {"false", "no", "n", "0", "否", "死亡", "死", "已死", "已死亡", "不是", "错"}
FORESHADOW_STATUSES = ("progressing", "resolved")
# 模型对伏笔状态的常见写法(2026-10-02 真实运行:写成 'planted' 导致整份入账被打回、整章重写)
_FS_ALIASES = {"推进": "progressing", "推进中": "progressing", "in_progress": "progressing", "progress": "progressing",
               "developing": "progressing", "回收": "resolved", "已回收": "resolved", "已收": "resolved",
               "closed": "resolved", "done": "resolved", "paid_off": "resolved"}
# "仍是埋着/没变化"本来就不是更新,丢掉即可,不值得为此打回整章
_FS_NOOP = {"planted", "埋下", "已埋", "open", "pending", "unchanged", "未变", "无变化"}


def to_bool(v, field: str) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(v)
    if isinstance(v, str) and v.strip().lower() in _TRUE:
        return True
    if isinstance(v, str) and v.strip().lower() in _FALSE:
        return False
    raise ParseError(f"{field}: 无法理解的布尔值 {v!r}")


def to_text(v, field: str) -> str:
    if v is None:
        return ""
    if isinstance(v, (str, int, float)) and not isinstance(v, bool):
        return str(v).strip()
    raise ParseError(f"{field}: 期望文本,得到 {type(v).__name__}")


def to_text_list(v, field: str) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        raise ParseError(f"{field}: 期望列表,得到 {type(v).__name__}")
    out = [to_text(x, field) for x in v]
    return list(dict.fromkeys(x for x in out if x))  # 去空、去重、保序


def to_int(v, field: str) -> int:
    if isinstance(v, bool):
        raise ParseError(f"{field}: 期望整数,得到布尔")
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().lstrip("#").isdigit():
        return int(v.strip().lstrip("#"))
    raise ParseError(f"{field}: 期望整数,得到 {v!r}")


def _list(d: dict, key: str) -> list:
    v = d.get(key)
    if v is None:
        return []
    if isinstance(v, dict):  # 只有一条时模型常直接给对象不套列表(2026-10-02 真实运行:因此整章重写)
        return [v]
    if not isinstance(v, list):
        raise ParseError(f"{key}: 期望列表,得到 {type(v).__name__}")
    return v


def normalize_character(c) -> dict:
    """只保留模型实际给出的字段(没给的交给 merge_character 沿用旧值)。"""
    if not isinstance(c, dict):
        raise ParseError(f"characters: 条目不是对象 {c!r}")
    name = to_text(c.get("name"), "characters.name")
    if not name:
        raise ParseError("characters: 条目缺少人名")
    out: dict = {"name": name}
    for k in ("location", "abilities", "relations", "profile"):
        if k in c:
            out[k] = to_text(c[k], f"characters.{k}")
    for k in ("alive", "core"):
        if k in c:
            out[k] = to_bool(c[k], f"characters.{k}")
    if "knows" in c:
        out["knows"] = to_text_list(c["knows"], "characters.knows")
    if "signature" in c:
        sig = normalize_signature(c["signature"])
        if sig:  # 空招牌不覆盖已有(模型给空对象当"没变化")
            out["signature"] = sig
    return out


def normalize_foreshadow_new(f) -> dict:
    if isinstance(f, str):
        f = {"content": f}
    if not isinstance(f, dict):
        raise ParseError(f"foreshadows_new: 条目无法理解 {f!r}")
    content = to_text(f.get("content"), "foreshadows_new.content")
    if not content:
        raise ParseError("foreshadows_new: 伏笔内容为空")
    return {"content": content, "payoff_plan": to_text(f.get("payoff_plan"), "foreshadows_new.payoff_plan"),
            "scale": normalize_scale(f.get("scale"))}  # 没填或写法不认识:按中线,不为这个打回整章


def normalize_foreshadow_update(u) -> dict | None:
    """返回 None 表示这条不是真正的更新("还埋着"),由调用方丢掉。"""
    if not isinstance(u, dict):
        raise ParseError(f"foreshadows_update: 条目不是对象 {u!r}")
    status = to_text(u.get("status"), "foreshadows_update.status").strip().lower()
    status = _FS_ALIASES.get(status, status)
    if status in _FS_NOOP:
        return None
    if status not in FORESHADOW_STATUSES:
        raise ParseError(f"foreshadows_update: 未知状态 {status!r}")
    return {"id": to_int(u.get("id"), "foreshadows_update.id"), "status": status}


# 2026-10-03 实测:让入账同时核对"正文内部的数字和算术"后,模型会把核对通过的结果也写进 contradictions
# ("……属策略性话术,不构成数字冲突""……正文承继一致")——而非有意的冲突会打回整章。一条干净的章被报了 2 条。
# 明说"不是冲突"的条目丢掉;只认明确的否定说法,"不一致""前后不一"之类的真冲突不受影响。
_NOT_A_CONFLICT = ("不冲突", "不算冲突", "无冲突", "没有冲突", "不构成", "不矛盾", "无矛盾", "并无矛盾", "核对通过", "无需登记", "承继一致")


def _says_no_conflict(text: str) -> bool:
    return any(p in text for p in _NOT_A_CONFLICT)


def normalize_contradiction(c) -> dict:
    if isinstance(c, str):
        c = {"what": c}
    if not isinstance(c, dict):
        raise ParseError(f"contradictions: 条目无法理解 {c!r}")
    planned = c.get("planned", False)
    return {"what": to_text(c.get("what"), "contradictions.what") or "(未说明的冲突)",
            # planned 无法理解时按 False:宁可误报重写,也不放过硬伤
            "planned": planned if isinstance(planned, bool) else _safe_bool(planned)}


def _safe_bool(v) -> bool:
    try:
        return to_bool(v, "planned")
    except ParseError:
        return False


def normalize_ledger(d: dict) -> dict:
    summary = to_text(d.get("summary"), "summary")
    if not summary:
        raise ParseError("summary 为空")
    return {
        "summary": summary,
        "characters": [normalize_character(c) for c in _list(d, "characters")],
        "foreshadows_new": [normalize_foreshadow_new(f) for f in _list(d, "foreshadows_new")],
        "foreshadows_update": [x for x in map(normalize_foreshadow_update, _list(d, "foreshadows_update")) if x],
        "facts": to_text_list(_list(d, "facts"), "facts"),
        "contradictions": [c for c in map(normalize_contradiction, _list(d, "contradictions")) if not _says_no_conflict(c["what"])],
        # 2026-10-03:编辑器"拿不准/建议/只提示"的观察放这里,不进 contradictions、不打回,只写运行记录供排查
        "editor_notes": to_text_list(_list(d, "editor_notes"), "editor_notes"),
        "devices": normalize_devices(d.get("devices")),
    }


def normalize_outline(d: dict) -> dict:
    title, outline = to_text(d.get("title"), "title"), to_text(d.get("outline"), "outline")
    if not title or not outline:
        raise ParseError("章纲缺少标题或内容")
    return {
        "title": title, "outline": outline, "hook": to_text(d.get("hook"), "hook"),
        "characters": to_text_list(d.get("characters"), "characters"),
        "foreshadows": [to_int(x, "foreshadows") for x in _list(d, "foreshadows")],
        "planned_reversals": to_text_list(d.get("planned_reversals"), "planned_reversals"),
        "payoff": to_text(d.get("payoff"), "payoff"),  # 提示里要求必填;解析时不因缺它打回整份章纲,工单里有就交给作者
        "novelty": to_text(d.get("novelty"), "novelty"),  # 可空:"类型惯例"档不要求
    }
