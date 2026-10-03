"""同一章里逐字重复的"有辨识度的长片段"。纯函数。

为什么(2026-10-03 读生产书,路线 57):"笑得像被雨打过的狗尾巴草"在一章里出现两次、相邻两章又逐字重复;
"暗兜里现在挤着四张纸条、三片碎纸……"也整句重来。这是开书样章里的比喻被模型当成了口头禅。

**不做硬打回**:实测 ≥12 字片段在章内重复 ≥3 次的只有 2/31 章,其中"除非你想知道那本书为什么等你"是**有意重复**的
文学手法——机械检查分不清"复沓"和"词穷"。所以这里只做**软提醒**:
- 把命中的片段写进运行记录(供排查);
- 章纲/正文提示要求编辑在正文里避免逐字重复(语义判断交给编辑与入账的 editor_notes)。
机械阈值只取"长 + 多次",宁漏不误伤(与 equator 57 的教训一致:误打回会导致干净章停更)。
"""
import re
from collections import Counter

HAN = re.compile("[一-鿿]")
PHRASE_N = 12   # 片段长度:短于此的多是地名/术语(实测 8 字命中率 25/31,噪音太大)
MIN_REPEAT = 3  # 章内出现这么多次才提示


def _han_only(text: str) -> str:
    return "".join(HAN.findall(text))


def repeated_phrases(body: str, names: list[str], n: int = PHRASE_N, k: int = MIN_REPEAT) -> list[str]:
    """章内重复 ≥k 次、长度 n 的汉字片段(含人名的排除:人名每章都在)。返回去重后的代表片段。"""
    t = _han_only(body or "")
    if len(t) < n:
        return []
    counts = Counter(t[i:i + n] for i in range(len(t) - n + 1))
    hits = [g for g, c in counts.items() if c >= k and not any(nm and nm in g for nm in names)]
    return sorted(set(hits), key=lambda g: t.index(g))


def repetition_note(body: str, names: list[str], limit: int = 3) -> str:
    """运行记录用的一句;没有命中返回空串。"""
    hits = repeated_phrases(body, names)[:limit]
    return ("本章有逐字重复的长片段:" + ";".join(hits)) if hits else ""


# 写进章纲/正文的提醒。语义层面:编辑比机械检查更能分清复沓与词穷。
RULE = ("同一章里不要逐字重复同一个比喻、句子或口头禅(开书样章里的一句话很容易被当成口头禅反复用);"
        "相邻两章之间更不要重复。要复沓(有意重复)时,让它一次比一次多出新的意思。")
