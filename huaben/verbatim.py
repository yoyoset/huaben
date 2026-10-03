"""章纲里的"原话":必须一字不改地出现在正文里。纯函数。

为什么(`docs/story-craft.md` 九·5):分量最重的句子(那句真心话、宣告的动作、触发反转的那一句、
新形态的解放语)不能交给写作模型现场发挥——它会把"我不跑了。"改写成"我不会再逃避了!",分量就没了。
所以这些句子由架构方在章纲里写死,写作模型必须原样用;没用上的,打回重写。
"""
import re

_IGNORED = re.compile(r"[\s\"'“”‘’「」『』]")  # 比对时不计空白与引号:模型常把直引号换成弯引号、在句中换行

# 半角标点 → 全角:章纲是架构方手写的,逗号问号常用半角,而正文是全角;句号不动(半角 . 会出现在数字和省略里)
_PUNCT_MAP = str.maketrans({",": "，", "?": "？", "!": "！", ":": "：", ";": "；", "(": "（", ")": "）"})


def _squash(text: str) -> str:
    return _IGNORED.sub("", text.translate(_PUNCT_MAP))


def missing_lines(body: str, lines: list[str]) -> list[str]:
    """章纲要求原样出现、正文里却找不到的句子。空白与引号的差异不算。"""
    hay = _squash(body)
    return [ln for ln in lines if _squash(ln) and _squash(ln) not in hay]


def lines_feedback(missing: list[str]) -> list[str]:
    """打回重写时给作者的话。"""
    return [f"工单要求原样写出的这句话没有出现在正文里,必须一字不改地写进去:{ln}" for ln in missing]


ENDING_WINDOW = 200  # 结尾原话必须落在正文最后这么多字里


def ending_problem(body: str, ending: str) -> list[str]:
    """章纲指定了结尾原话,正文却没有停在那里(没出现,或出现之后又往下写了一大段)。"""
    want = _squash(ending or "")
    if not want:
        return []
    hay = _squash(body)
    if want not in hay:
        return [f"正文没有写到工单指定的结尾。最后一句必须是(一字不改):{ending}"]
    if want not in hay[-ENDING_WINDOW:]:
        return [f"正文写过头了:工单指定的结尾“{ending}”出现之后又往下写了一大段。写到这句就停,后面的事留给下一章,把多出来的全部删掉。"]
    return []
