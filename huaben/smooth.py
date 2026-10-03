"""接句:把被逗号切碎的正文交给写作模型接顺,并用机械检查核对改稿。纯函数。

只动标点,不动情节:改稿与原稿去掉标点空白后必须几乎一字不差,段数不能变,章纲原话不能动。
"""
import difflib
import re

from .pipeline.chop import comma_density
from .verbatim import missing_lines

SMOOTH_TARGET = 8.5      # 改完后每百字逗号数不超过它才算接顺
MIN_SIMILARITY = 0.995   # 去掉标点与空白后,改稿与原稿的相似度下限
MAX_PARA_DRIFT = 0.02    # 段数允许的相对偏差

SYSTEM = """你是一位中文小说的文字编辑，只做一件事：把被逗号切碎的句子接回成自然、利落的句子。

这份稿子的毛病：作者为了显得沉重，把一句话切成很多小段，例如“陈皮的血，一下子，冲上了头”“木板，翻开了”“它们，没有看他的脸”。读起来做作，朗读时一顿一顿。

怎么改：
1. 主语和谓语之间的逗号去掉：“木板，翻开了” → “木板翻开了”；“陈皮的手，停了” → “陈皮的手停了”。
2. 状语、连词后面多余的逗号去掉：“陈皮的血，一下子，冲上了头” → “陈皮的血一下子冲上了头”。
3. 一串两三个字的小段并成一句：“伸手，把那团东西，勾了过来” → “伸手把那团东西勾了过来”。
4. 人物说的话里同样的碎逗号也照此接上：“潭里，没有大鱼。” → “潭里没有大鱼。”。结巴（“到、到了”）、省略号、破折号不动。

只许删掉或改动标点。绝对不能动的：
- 任何一个字词：不许增、删、换，不许加主语，不许调换语序。
- 分段：每一段还是那一段，不许合并或拆分。
- 用户消息里“不许动的原话”列出的句子：一个字、一个标点都不许改。

目标的松紧是这样的（同一本书前面的章）：
“他把锄头靠在牌坊柱子上，擦了擦手，接过铺盖卷，往肩上一搭，慢吞吞走在前头。陈皮跟在后面，两手空空，腰里的断剑一晃一晃，神气得像个来巡视的。”

只输出改好的整章正文，从第一句到最后一句，不要任何说明、标题或前后缀。"""


def strip_punct(text: str) -> str:
    """去掉所有空白与标点(中文、英文标点和各种引号、省略号、破折号),只留字。"""
    return re.sub(r"[\W_]", "", text, flags=re.UNICODE)


def smooth_messages(body: str, lines: list[str], feedback: list[str]) -> list[dict]:
    """[system, user]。user = 下面的"用户消息"格式。"""
    parts = []
    if lines:
        parts.append("不许动的原话:\n" + "\n".join(f"- {s}" for s in lines))
    if feedback:
        parts.append("上一稿的问题,这一稿必须改掉:\n" + "\n".join(f"- {f}" for f in feedback))
    parts.append("下面是要改的正文:\n\n" + body)
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n\n".join(parts)}]


def _paras(text: str) -> int:
    return len([p for p in text.split("\n") if p.strip()])


def smooth_problems(old: str, new: str, lines: list[str]) -> list[str]:
    """改稿不能用的理由(硬伤);空列表 = 可以用。只查硬伤,不查逗号密度。"""
    out = []
    r = difflib.SequenceMatcher(None, strip_punct(old), strip_punct(new), autojunk=False).ratio()
    if r < MIN_SIMILARITY:
        out.append(f"改动了文字(相似度 {r:.3f}):只许改标点和断句,不许增删改任何字词。")
    for ln in missing_lines(new, lines):
        out.append(f"这句原话被改了,必须一字一标点照原样:{ln}")
    a, b = _paras(old), _paras(new)
    if abs(a - b) / (max(a, b) or 1) > MAX_PARA_DRIFT:
        out.append(f"段数变了({a} → {b}):不许合并或拆分段落。")
    old_n, new_n = len(re.sub(r"\s", "", old)), len(re.sub(r"\s", "", new))
    if new_n < old_n * 0.9:
        out.append(f"稿子不完整(只有原文的 {new_n / old_n:.0%}):必须从第一句改到最后一句。")
    return out
