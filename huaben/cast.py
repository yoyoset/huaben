"""人物志:把账本里的人物现状整理成读者能读的一页(路线 61)。

现状只存在于数据库里,只有模型看得到。读者想回顾"这个角色是谁、能力是什么、跟主角什么关系"时没有入口。
纯函数:把 list_characters 的结果整形;不碰数据库。
"""
MAX_KNOWN = 6  # 每人最多列几条"知道",太多就淹没了重点


def build(rows: list[dict], bible: dict | None = None) -> list[dict]:
    """账本人物 → 人物志条目。按"核心在前、其余按名字"的顺序(与 list_characters 一致)。
    没出场过的路人(updated_ch=0)也列,但排在最后——读者可能只想看已登场的。"""
    bible = bible or {}
    roles = {c.get("name"): c.get("role", "") for c in bible.get("characters") or []}
    out = []
    for c in rows:
        sig = c.get("signature") or {}
        out.append({
            "name": c["name"],
            "alive": c["alive"],
            "core": c["core"],
            "role": roles.get(c["name"], ""),      # 来自开书人物卡;中途登场的为空
            "profile": c.get("profile", ""),
            "location": c.get("location", ""),
            "abilities": c.get("abilities", ""),
            "signature": {"name": sig.get("name", ""), "rule": sig.get("rule", ""),
                          "stage": sig.get("stage", ""), "next": sig.get("next", "")} if sig else {},
            "signature_text": _signature_text(sig),
            "relations": c.get("relations", ""),
            "knows": list(c.get("knows") or [])[:MAX_KNOWN],
            "knows_more": max(len(c.get("knows") or []) - MAX_KNOWN, 0),
            "updated_ch": c.get("updated_ch", 0),
        })
    # 已登场的排前面(updated_ch>0),其中核心再优先;没登场过的沉底
    return sorted(out, key=lambda x: (x["updated_ch"] == 0, not x["core"], x["name"]))


def _signature_text(sig: dict) -> str:
    if not sig or not sig.get("name"):
        return ""
    parts = [sig["name"]]
    if sig.get("rule"):
        parts.append(sig["rule"])
    if sig.get("stage"):
        parts.append(f"当前:{sig['stage']}")
    if sig.get("next"):
        parts.append(f"下一阶:{sig['next']}")
    return "——".join([parts[0], ";".join(parts[1:])]) if len(parts) > 1 else parts[0]
