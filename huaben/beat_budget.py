"""每个节拍分配多少章:把卷的总章数按节拍分量分配,而不是平均摊。纯函数。

为什么(2026-10-03 用户:"都四章了,连山门都还没进";但也不能一章都快——要有快有慢,由情节决定):
旧的 `rules.pacing_rule` 用平均公式算出本章该写哪个节拍:
    i = min(len(beats), ctx.volume_done * len(beats) // target + 1)
每个节拍不管轻重都拿到同样多的章。实测后果:
- 《算尽仙朝》32 章 / 10 个节拍 = 每节拍 3.2 章。第 1 个节拍只是"镇上算账、决定去考"这种开场过渡,
  也被摊了 3 章,于是第 1~3 章还在镇上和路上,第 4 章才到山门口核验户籍,第 5 章才进考场。
- 《杂役仙尊》30 章 / 11 个节拍。第 5 个节拍"偷学功法被撞破"是一场小戏,被摊了 3 章,
  于是第 12、13、14 章把"划字练气、被沈青梧撞破、重申互不揭发"原样演了三遍。

所以"慢"和"重演"是同一个病:小节拍被硬撑成好几章。真正要的是**章数按节拍的分量分配**——
过渡 1 章,重头戏 3~5 章,卷的总章数 = 各节拍章数之和。位置仍由程序按已写章数算出,
不让模型判断"这个节拍写完没有"。
"""
MIN_PER_BEAT, MAX_PER_BEAT = 1, 8

BUDGET_RULE = ("给每个节拍分配章数(beat_chapters,与 beats 一一对应、等长):不要平均分。"
               "过渡性的节拍(赶路、报到、办手续、领差事、日常、打听消息)只给 1 章;"
               "重头戏(对决、摊牌、谷底、高潮、关键揭秘)给 3~5 章;其余给 2 章。"
               "读者要看的是戏,不是流程——进门、报到、办手续这类事必须一章之内走完。"
               "target_chapters 等于 beat_chapters 之和。")


def normalize_budget(raw, beat_count: int) -> list[int] | None:
    """模型给的 beat_chapters → 合法形状;长度对不上或不是整数就返回 None(调用方退回平均算法)。"""
    if not isinstance(raw, list) or not beat_count or len(raw) != beat_count:
        return None
    if any(isinstance(x, bool) or not isinstance(x, int) for x in raw):
        return None
    return [min(max(x, MIN_PER_BEAT), MAX_PER_BEAT) for x in raw]


def locate(budget: list[int], done: int) -> tuple[int, int, int]:
    """→ (i, k, n):本章在第 i 个节拍(从 1 起)、是它的第 k 章、它一共 n 章。done = 本卷已定稿章数。
    预算为 0 的节拍跳过(T004 给旧卷补预算时,已走完的节拍可能是 0)。写超了就停在最后一个节拍的最后一章。"""
    acc = 0
    for i, n in enumerate(budget, 1):
        if n and done < acc + n:
            return i, done - acc + 1, n
        acc += n
    last = max((i for i, n in enumerate(budget, 1) if n), default=len(budget))
    return last, budget[last - 1], budget[last - 1]


def beat_line(beats: list[str], i: int, k: int, n: int) -> str:
    """节奏要求的一句。n == 0 表示没有预算(旧卷),只说大约在哪个节拍。"""
    head = f"第 {i}/{len(beats)} 个节拍「{beats[i - 1]}」"
    if n == 0:
        return f"节奏:按进度,本章大约应推进{head}。"
    nxt = f"「{beats[i]}」" if i < len(beats) else "本卷的收尾"
    if n == 1:
        return (f"节奏:{head}只给 1 章,就是本章——这是过渡,快写:赶路、手续、日常用一两句概述带过,时间可以跳,"
                f"不要把每一步都写成一场戏;本章结束时这个节拍必须已经走完,人物站到{nxt}的门口。")
    if k >= n:
        return (f"节奏:{head}共 {n} 章,本章是最后一章——必须把这个节拍收完,不许再拖到下一章;"
                f"下一章就要进入{nxt}。")
    if n == 2:
        return (f"节奏:{head}共 2 章,本章是第 1 章——正常推进,把这个节拍走到一半以上;"
                f"本章必须有一个上一章没有的实质进展(局面、信息或关系变了),不要把上一章的事再演一遍。")
    return (f"节奏:{head}是重头戏,共 {n} 章,本章是第 {k} 章——慢下来把这场戏写足;"
            f"但本章必须有一个上一章没有的实质进展(局面、信息或关系变了),不要把上一章的事再演一遍。")
