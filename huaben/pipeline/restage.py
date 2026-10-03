"""打回"重演上一章"的稿子。纯函数。

为什么(2026-10-03 读生产书):《杂役仙尊》第 13、14 章开场几乎一样(雾、飞檐只露一个尖、枣树下练气后背出汗、
沈青梧拎篮子从树后出来),《算尽仙朝》第 9 章把第 8 章的查账又算了一遍——12 字片段的照抄检查抓不到这种换了说法的重演。
阈值来自生产两本书 23 对相邻章的实测(人名不计,人名本来就每章都有):
- 开场前 300 字的汉字二元组 Jaccard:正常 0.01~0.08,重演的第 14 章 0.15;
- 全章 6 字片段与上一章的重合(交集 / 较小者):正常 0.004~0.047,重演的第 13、14 章 0.082/0.087,重算的第 9 章 0.068。
"""
import re

OPENING_CHARS = 300
OPENING_LIMIT = 0.12
PHRASE_N = 6
PHRASE_LIMIT = 0.06
MIN_HAN = 200  # 太短的文本比相似度没有意义(几十个字里"他把""走到"就能撞上一大半)
_HAN = re.compile("[一-鿿]")


def _grams(text: str, n: int, names: list[str]) -> set[str]:
    t = "".join(_HAN.findall(text))
    gs = {t[i:i + n] for i in range(len(t) - n + 1)}
    # 含人名的片段不算:"周小满""沈青梧"每章都在,不代表重演
    return {g for g in gs if not any(nm and (nm in g or g in nm) for nm in names)}


def opening_similarity(text: str, prev: str, names: list[str]) -> float:
    a, b = _grams(text[:OPENING_CHARS], 2, names), _grams(prev[:OPENING_CHARS], 2, names)
    return len(a & b) / len(a | b) if a and b else 0.0


def phrase_overlap(text: str, prev: str, names: list[str]) -> float:
    a, b = _grams(text, PHRASE_N, names), _grams(prev, PHRASE_N, names)
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def restage_problems(text: str, prev: str, names: list[str]) -> list[str]:
    """prev:上一章正文(第一章时为空)。返回打回理由;空 = 通过。两边任一太短(篇幅检查另管)就不比。"""
    if len(_HAN.findall(text)) < MIN_HAN or len(_HAN.findall(prev)) < MIN_HAN:
        return []
    problems = []
    if opening_similarity(text, prev, names) > OPENING_LIMIT:
        problems.append("开场和上一章几乎一样(同样的时间、地点、动作):从上一章结束之后接着写,换一个开场")
    if phrase_overlap(text, prev, names) > PHRASE_LIMIT:
        problems.append("这一稿和上一章有大段相同的场景和说法,像把上一章又演了一遍:"
                        "上一章已经发生的事、已经说出的信息不要再写,往前推进新的事")
    return problems
