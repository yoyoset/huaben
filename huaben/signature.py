"""角色的"招牌能力"与成长阶段。纯函数。

为什么(2026-10-03 用户:要能写出《海贼王》《火影》《死神》那种故事):
那三部里每个重要角色都有**一眼认得出的招牌能力**——恶魔果实、忍术、斩魄刀——有名字、有明确的规则与代价、
有独有的形态,而且**随剧情进阶**(二档、须佐能乎、卍解),进阶本身就是一个爽点。
现有账本把人物的能力当一段自由文本("能力:夜视"),没有"招牌/阶段"的概念,模型于是每章随手给主角一个万能能力,
成长也不可见——这是"大师级基底"里最先要补的一格。

形状(存 ledger_characters.signature,JSON 文本;旧数据为空):
    {"name": 招牌能力名, "rule": 一句话规则或代价, "stage": 当前形态/阶段, "next": 下一阶段(可空)}
空字典 = 还没定招牌(老角色、路人),渲染时直接跳过,不要为它打回入账。
"""
import json

FIELDS = ("name", "rule", "stage", "next")
NAME_MAX, TEXT_MAX = 20, 80


def normalize_signature(raw) -> dict:
    """认不出的当"还没定",不为它打回整份入账。name 为空即视为没有招牌。"""
    if isinstance(raw, str):  # 模型偶尔只给一个能力名
        raw = {"name": raw}
    if not isinstance(raw, dict):
        return {}
    out = {k: str(raw.get(k) or "").strip()[:TEXT_MAX] for k in FIELDS}
    out["name"] = out["name"][:NAME_MAX]
    return out if out["name"] else {}


def to_json(sig: dict) -> str:
    return json.dumps(sig, ensure_ascii=False)


def from_json(text: str) -> dict:
    """DB 里的 JSON 文本 → 招牌能力。坏数据当空(不让一本老书因为这个读不出来)。"""
    try:
        return normalize_signature(json.loads(text or "{}"))
    except ValueError:
        return {}


def render(sig: dict) -> str:
    """人物现状那一行里的"招牌"片段;没有招牌返回空串。"""
    sig = normalize_signature(sig)
    if not sig:
        return ""
    parts = [sig["name"]]
    if sig["rule"]:
        parts.append(sig["rule"])
    if sig["stage"]:
        parts.append(f"当前:{sig['stage']}")
    if sig["next"]:
        parts.append(f"下一阶:{sig['next']}")
    return "招牌:" + "——".join([parts[0], ";".join(parts[1:])]) if len(parts) > 1 else f"招牌:{parts[0]}"


def advance(old: dict, new: dict) -> bool:
    """本次入账是否让招牌"进阶"(换了阶段文字)。进阶要被当成一个爽点来写,而不是随口一提。"""
    o, n = normalize_signature(old), normalize_signature(new)
    return bool(n.get("stage")) and n["stage"] != o.get("stage")


# 写进章纲/正文的硬要求。挂在写法设定的想象力档位上太重——招牌能力对任何类型都有用,所以独立成规则。
RULE = ("重要角色打斗、解决问题,要**靠自己的招牌能力**——有名有姓、有明确的规则与代价、有独有的样子,"
        "而不是临时冒出一个万能的新能力。招牌能力可以进阶(得到新形态),但每次进阶都必须是本章/本卷的爽点,"
        "靠自己挣来(顿悟、苦练、付出代价),不能凭空获得。")


def rule_for_core() -> str:
    return RULE
