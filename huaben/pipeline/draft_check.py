"""正文的机械质量底线。纯函数:能自动清理的就清理,清理不了的作为"打回理由"交给重写。

这些检查不评判好不好看,只拦"明显不是一章小说"的稿子——否则它会被定稿、配音、推给读者,
而入账核对只看设定冲突,发现不了这类问题。
"""
import re

MIN_LENGTH_RATIO = 0.4      # 少于目标字数的 40%:篇幅不足
MIN_PUNCT_DENSITY = 1 / 60  # 每 60 字至少 1 个中文标点。前身踩坑:惩罚参数非 0 时长章后半段标点全部消失
TAIL_WINDOW = 600           # 标点密度单独查最后这么多字(标点消失总是发生在后半段)
REPEAT_LIMIT = 3            # 同一段落出现 ≥3 次视为生成退化

_PUNCT = re.compile(r"[,。!?;:、“”‘’…—「」『』(),!?]")
_HEADING = re.compile(r"^\s*(#+\s*|第\s*[0-9一二三四五六七八九十百千零〇]+\s*章|标题\s*[::]|《[^》]{1,30}》\s*$)")
_TRAILER = re.compile(r"^\s*[((【\[]?\s*(本章完|全章完|完|未完待续|待续)\s*[))】\]]?\s*$")
_REFUSAL = re.compile(r"抱歉|对不起,我|我无法|我不能(为你|帮你|提供|创作|继续)|作为(一个)?\s*(AI|人工智能|语言模型)"
                      r"|I'?m sorry|I cannot|I can't|as an AI", re.I)


def content_length(text: str) -> int:
    return len(re.sub(r"\s", "", text))


def clean_draft(text: str) -> str:
    """去掉模型常加的开头标题行与结尾"本章完"之类,正文本身不动。"""
    lines = text.strip().splitlines()
    # 只在后面还有正文时才当标题去掉;像标题的句子若是全部内容,保留原样交给篇幅检查
    while len(lines) > 1 and len(lines[0].strip()) <= 40 and not re.search(r"[。!?!?]", lines[0]) \
            and _HEADING.match(lines[0]):
        lines.pop(0)
    while lines and _TRAILER.match(lines[-1]):
        lines.pop()
    return "\n".join(lines).strip()


def draft_problems(text: str, target_words: int) -> list[str]:
    """返回打回理由(写给作者看的人话);空列表 = 通过。text 应是 clean_draft 之后的。"""
    problems: list[str] = []
    n = content_length(text)
    if n < target_words * MIN_LENGTH_RATIO:
        problems.append(f"篇幅不足:只有约 {n} 字,目标约 {target_words} 字,请写成完整的一章")
    if _REFUSAL.search(text[:300]):
        problems.append("上一稿不是小说正文(像是拒绝或说明),请直接写这一章的故事")
    tail = re.sub(r"\s", "", text)[-TAIL_WINDOW:]
    if len(tail) >= 200 and len(_PUNCT.findall(tail)) < len(tail) * MIN_PUNCT_DENSITY:
        problems.append("后半部分标点缺失、句子粘连,请全文使用完整的中文标点")
    paras = [p.strip() for p in text.split("\n") if len(p.strip()) >= 15]
    if paras and max(paras.count(p) for p in set(paras)) >= REPEAT_LIMIT:
        problems.append("出现大段重复的段落,请不要重复")
    return problems
