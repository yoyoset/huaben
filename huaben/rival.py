"""长期对手(宿敌):会跟主角一起成长的那种对手。纯函数,不碰数据库。

为什么(2026-10-03 用户:要能写出《海贼王》《火影》《死神》那种故事):
那三部的"上头"很大程度靠长期对手——索隆/鹰眼、鸣人/佐助、一护/白哉——他们**不是一次性的 boss**,
而是每隔几卷回来一次,而且**每次回来都更强**,主角的成长因此有了标尺。
现在系统里每卷有一个对手(arc.antagonist),但卷与卷之间对手可以完全不相干,长期对手没有被点名保留、也没有要求他成长。
做法:开书时从人物卡里标出 1~2 个长期对手;卷规划时要求让至少一个长期对手有实质变化(变强/立场变/代价),不许悄悄消失。
"""
MAX_RIVALS = 3


def from_bible(bible: dict | None) -> list[str]:
    """圣经人物卡里标了 rival 的人名(去重、按卡的顺序)。旧书没有这个标记 → 空,不强行编造。"""
    out: list[str] = []
    for c in (bible or {}).get("characters") or []:
        name = str(c.get("name", "")).strip()
        if name and c.get("rival") and name not in out:
            out.append(name)
    return out[:MAX_RIVALS]


def render(rivals: list[str]) -> str:
    if not rivals:
        return ""
    return ("【长期对手(宿敌)】" + "、".join(rivals)
            + ":他们不是一次性的对手,要隔几卷回来一次,而且每次回来都比上次更强或更难对付;"
            "主角的成长以他们为标尺。")


def advance_rule(rivals: list[str], used: list[str]) -> str:
    """卷规划提示:让至少一个长期对手在本卷有实质变化。used:往卷已经推进过的对手(留痕用)。"""
    if not rivals:
        return ""
    already = f"(往卷已推进:{';'.join(used)})。" if used else ""
    return ("本卷要让至少一个长期对手有实质变化:变强、换立场、暴露新的一面,或付出代价——"
            "不能让他悄悄消失或原地踏步;他是读者衡量主角成长的标尺。" + already)


def advanced_by(volumes: list[dict], rivals: list[str]) -> list[str]:
    """往卷里已经把哪些长期对手当成本卷主要对手(arc.antagonist 里出现其名)。用于提示"别只推进同一个"。"""
    out: list[str] = []
    for v in volumes:
        antagonist = str((v.get("arc") or {}).get("antagonist") or "")
        for name in rivals:
            if name and name in antagonist and name not in out:
                out.append(f"第{v['idx']}卷:{name}")
    return out

