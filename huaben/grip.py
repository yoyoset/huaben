"""章纲的松紧档:哪些不能错、哪些放开写。纯函数。

为什么(2026-10-04 用户:"章纲也要分级。哪些是原则性逻辑问题,哪些是自由度高的问题……加戏可以,大方向对就可以"):
细到"第几场、谁说哪句、结尾句一字不改"的章纲,日常章也这么管,写作模型要么卡在收尾上反复重写,要么把活写死。
所以每章标一个档:关键章管得严、日常章放开,真正不能错的事单独列出来。没填按"紧"算(老书行为不变)。
"""
GRIPS = ("紧", "中", "松")
MUST_PREFIX = "不能错:"

_FIRST_LINE = {
    "紧": "本章是关键章:场次、顺序、每一场的结果都照工单写,不要增删场次;对白可以润色。",
    "中": "工单是骨架:有哪几场、每一场的结果照办;骨架之间的对白、玩笑、人物的小动作可以自己加,可以接前面章节的包袱。",
    "松": "本章放开写:只要下面\"不能错的\"几条和结尾落点对,场次怎么排、加什么戏由你定,写得活比写得全要紧。",
}
_ENDING_STRICT = "本章最后一句必须是(一字不改),写到这句就停,不要再往下写——后面的事是下一章的:"
_ENDING_LOOSE = "本章结尾停在下面这一刻(意思到了就行,字句可以自己写),写到这里就停,不要再往下写——后面的事是下一章的:"


def grip_of(outline: dict) -> str:
    """章纲的松紧档;没填或填了别的,按"紧"。"""
    grip = outline.get("grip")
    return grip if grip in GRIPS else "紧"


def grip_lines(outline: dict) -> list[str]:
    """工单里交代松紧的几行;放在工单正文之后。"""
    lines = [_FIRST_LINE[grip_of(outline)]]
    must = [m for m in (outline.get("must") or []) if m]
    if must:
        lines.append("【不能错的】(违反任何一条,整稿作废):")
        lines += [f"- {m}" for m in must]
    if outline.get("free"):
        lines.append(f"【可以发挥的】{outline['free']}")
    return lines


def ending_line(outline: dict) -> str | None:
    """工单里交代结尾的那一行;章纲没有 ending 返回 None。"""
    ending = outline.get("ending") or ""
    if not ending:
        return None
    prefix = _ENDING_STRICT if grip_of(outline) == "紧" else _ENDING_LOOSE
    return f"{prefix}{ending}"


def check_ending(outline: dict) -> bool:
    """这一章的结尾原话要不要硬查:只有"紧"查。"""
    return grip_of(outline) == "紧"


def hard_contradictions(outline: dict, bad: list[str]) -> list[str]:
    """编辑核对挑出的矛盾里,哪些要打回:"紧"= 全部;"中""松"= 只有以 MUST_PREFIX 开头的。"""
    if grip_of(outline) == "紧":
        return list(bad)
    return [b for b in bad if b.startswith(MUST_PREFIX)]


def lenient(outline: dict, attempt: int, max_attempts: int) -> bool:
    """这一稿是不是"末稿放行":档位不是"紧",而且是最后一稿,而且总稿数大于 1。

    为什么(2026-10-04 实测:mimo 第 17 章、deepseek 第 22 章都卡在"结尾句差几个字"上反复重写):
    "读者没有下一章可读"比"结尾句差几个字"糟得多。中、松档的最后一稿,重的问题(缺原话、
    结尾、碎句)不再打回,留痕放行;致命的(篇幅、照抄、矛盾)哪一稿都拦。只有一稿可写时
    不适用——放行等于无条件通过,不如照常失败让重试机制接手。
    """
    return grip_of(outline) != "紧" and max_attempts > 1 and attempt >= max_attempts


def must_block(outline: dict) -> str:
    """给编辑核对用的一段;章纲没有 must 返回空字符串。"""
    must = [m for m in (outline.get("must") or []) if m]
    if not must:
        return ""
    lines = ["【本章不能错的】", *[f"- {m}" for m in must],
             "正文违反上面任何一条,写进 contradictions,what 以\"不能错:\"开头,planned 填 false。"]
    return "\n".join(lines)
