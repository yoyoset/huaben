"""推动情节的"手段"别一用再用。纯函数。

为什么(2026-10-03 生产实测):《算尽仙朝》前 10 章每章都有"算盘残片发烫、浮现一行字"(残片一词每章 3~12 次),
《杂役仙尊》14 章里 12 章靠"枕头下的纸条"传信(纸条一词最多一章 18 次)。结尾钩子去重(prompts.recent_hooks)
管不到正文;按字词统计又分不清"反复出现的地点"(正常)和"反复用的把戏"(腻)——实测高频词里混满了"采买司""藏经阁""了一"。
所以让入账的编辑顺手登记本章用了哪些推动情节/制造悬念的手段,同名沿用;规划下一章时把最近几章反复用的点出来。
"""
MAX_DEVICES = 5
MAX_LEN = 12
REPEAT_IN = 2  # 最近几章里有这么多章用过,就算"反复用"


def normalize_devices(raw) -> list[str]:
    """入账给的手段 → 去空、去重、截短、最多 MAX_DEVICES 条。认不出就当没有,不为这个打回入账。"""
    items = raw if isinstance(raw, list) else [raw] if isinstance(raw, str) else []
    out: list[str] = []
    for x in items:
        s = str(x).strip()[:MAX_LEN]
        if s and s not in out:
            out.append(s)
    return out[:MAX_DEVICES]


def overused(recent: list[list[str]], at_least: int = REPEAT_IN) -> list[tuple[str, int]]:
    """recent:最近几章各自的手段。返回 (手段, 用过的章数),按次数从多到少。"""
    counts: dict[str, int] = {}
    for chapter in recent:
        for d in set(chapter):
            counts[d] = counts.get(d, 0) + 1
    return sorted(((d, n) for d, n in counts.items() if n >= at_least), key=lambda x: (-x[1], x[0]))


def known_list(recent: list[list[str]]) -> str:
    """给入账编辑看的"最近用过的手段":同一个手段沿用原名,统计才对得上。"""
    names = sorted({d for chapter in recent for d in chapter})
    return "、".join(names) if names else "(无)"


def avoid_rule(recent: list[list[str]]) -> str:
    """写进章纲/正文提示的一句;没有反复用的就为空。"""
    hits = overused(recent)
    if not hits:
        return ""
    listed = "、".join(f"{d}({n}/{len(recent)} 章)" for d, n in hits)
    return (f"最近几章反复用来推动情节的手段:{listed}。本章不要再用它们推动情节或制造悬念;"
            "换成人物自己的选择、对手的行动、新的地方或新的设定。")


def from_rows(rows: list[dict]) -> list[list[str]]:
    """章记录(chapters.devices 是 JSON 文本;旧章为空)→ 各章的手段。坏数据当没有。"""
    import json
    out = []
    for r in rows:
        try:
            out.append(normalize_devices(json.loads(r.get("devices") or "[]")))
        except ValueError:
            out.append([])
    return out
