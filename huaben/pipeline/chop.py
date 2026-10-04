"""碎句检查:句子被逗号切碎的稿子,超过硬线打回重写。纯函数。

为什么(2026-10-03 回看《弄假成真》第 3~30 章,架构方在同一个对话里一口气写的):句子越写越碎。
实测每百字的全角逗号数:第 1~8 章约 7,第 12~18 章 9~10,第 19~30 章 10.3~12.4。
第 30 章满篇是"陈皮的血,一下子,冲上了头""木板,翻开了"这种句子,看着做作,配音会一顿一顿。
原因是"自己学自己":前面写出的章留在上下文里,下一章照着模仿并加码;写作模型按章写时带着最近 3 章原文,同样会漂。

为什么分两段(T030,2026-10-04 用户:"不能一刀切")——实测正常的章 6~8,真切碎的章 10 以上:
9.0 到 10.0 之间只是偏碎,不值得整稿打回重写,留痕供对账即可;大于 10.0 才是真碎,打回。
"""
import re

CHOP_HARD = 10.0        # 打回线:每百字全角逗号数大于它才算切碎,打回重写(实测切碎的章 10 以上)
CHOP_LIMIT = 9.0        # 提醒线:大于它、又不大于 CHOP_HARD,只留痕不打回
CHOP_MIN_CHARS = 500    # 太短的文本不量(样本小,数字不稳)


def comma_density(text: str) -> float:
    """每 100 个非空白字符里有几个全角逗号"，"。空文本返回 0.0。"""
    chars = len(re.sub(r"\s", "", text))
    if not chars:
        return 0.0
    return text.count("，") / chars * 100


def _too_short(text: str) -> bool:
    return len(re.sub(r"\s", "", text)) < CHOP_MIN_CHARS


def chop_problems(text: str) -> list[str]:
    """密度大于 CHOP_HARD → 一条打回理由;否则空列表。非空白字符不足 CHOP_MIN_CHARS → 空列表。"""
    if _too_short(text):
        return []
    d = comma_density(text)
    if d <= CHOP_HARD:
        return []
    return [f"句子被逗号切得太碎（每百字 {d:.1f} 个逗号，正常是 6~8 个）：主语和谓语之间不要加逗号，“他的手，停了”要写成“他的手停了”；不要把一句话切成一串两三个字的小段。请把句子接顺再写一稿。"]


def chop_note(text: str) -> str:
    """密度大于 CHOP_LIMIT 且不大于 CHOP_HARD → 一句提醒;否则空字符串。非空白字符不足 CHOP_MIN_CHARS → 空字符串。"""
    if _too_short(text):
        return ""
    d = comma_density(text)
    if CHOP_LIMIT < d <= CHOP_HARD:
        return f"句子偏碎(每百字 {d:.1f} 个逗号,正常是 6~8 个)"
    return ""
