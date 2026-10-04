"""节奏检查:章纲带五个标记(mode/tension/result/gain/turn),导入时把不合拍的地方列出来。

为什么(2026-10-03 用户:"所有都应该有节奏。进度有节奏,力量路线有节奏,剧情起伏也应该有节奏。有困难才有感动。"):
节奏的规矩写在 `docs/story-craft.md` 第五节(口味轮换、压与放、胜负密度、力量所得的间隔),但规矩只写在文档里就只能靠写章纲的人自觉——
此前"四章没进山门""连续三章重演同一场戏"都是没人检查节奏的结果。
检查结果是**提醒**,不是拦截:有的不合拍是有意的(比如决战连打五章),由导入的人决定改不改。

`turn` = 这一章的反转有多大。小 = 局面/信息/关系变了一下;中 = 一个目标、一个局、一份代价翻了;
大 = 改变读者对一个人或一件事的整体看法。可以不填,不填当无。只查"太密",不查"必须有几个"。
"""
import json
import sys
from pathlib import Path

from .grip import GRIPS, grip_of

MODES = ("战", "笑", "情", "谜", "修")
RESULTS = ("胜", "负", "平", "无")
TURNS = ("无", "小", "中", "大")


def _words_ok(v) -> bool:
    """章纲里的本章目标字数是否合法:800~8000 的整数(字符串数字也认);bool 不算整数。"""
    if isinstance(v, bool):
        return False
    if isinstance(v, str) and v.strip().isdigit():
        v = int(v.strip())
    return isinstance(v, int) and 800 <= v <= 8000


def _runs(flags: list[bool]) -> list[tuple[int, int]]:
    """连续为真的区间,返回 [(起始下标, 长度)]。"""
    out, start = [], None
    for i, f in enumerate([*flags, False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i - start))
            start = None
    return out


def rhythm_problems(chapters: list[dict]) -> list[str]:
    """标记本身不合法(缺栏、取值不对)。这类是硬问题,导入要拦。"""
    problems = []
    for n, ch in enumerate(chapters, 1):
        if ch.get("mode") not in MODES:
            problems.append(f"第 {n} 章 mode 必须是 {'/'.join(MODES)} 之一")
        t = ch.get("tension")
        if isinstance(t, bool) or not isinstance(t, int) or not 1 <= t <= 5:
            problems.append(f"第 {n} 章 tension 必须是 1~5 的整数")
        if ch.get("result") not in RESULTS:
            problems.append(f"第 {n} 章 result 必须是 {'/'.join(RESULTS)} 之一")
        if (ch.get("turn") or "无") not in TURNS:
            problems.append(f"第 {n} 章 turn 必须是 {'/'.join(TURNS)} 之一(可不填)")
        if ch.get("grip") and ch["grip"] not in GRIPS:
            problems.append(f"第 {n} 章 grip 必须是 {'/'.join(GRIPS)} 之一(可不填)")
        if ch.get("words") not in (None, "") and not _words_ok(ch["words"]):
            problems.append(f"第 {n} 章 words 必须是 800~8000 的整数(可不填)")
    return problems


def rhythm_warnings(chapters: list[dict]) -> list[str]:
    """节奏提醒(不拦导入)。chapters 的标记须已通过 rhythm_problems。章号按本批从 1 数。"""
    w, n = [], len(chapters)
    modes = [c["mode"] for c in chapters]
    tension = [c["tension"] for c in chapters]
    wins = [c["result"] == "胜" for c in chapters]
    gains = [bool(str(c.get("gain") or "").strip()) for c in chapters]

    for m in MODES:  # 同一种口味连续太久
        for start, length in _runs([x == m for x in modes]):
            if length > (5 if m == "战" else 3):
                w.append(f"第 {start + 1}~{start + length} 章连续 {length} 章都是「{m}」")
    for start, length in _runs([t >= 4 for t in tension]):  # 一直绷着
        if length > 4:
            w.append(f"第 {start + 1}~{start + length} 章连续 {length} 章张力都在 4 以上,中间没有喘气")
    for start, length in _runs([t <= 2 for t in tension]):  # 一直松着
        if length > 3:
            w.append(f"第 {start + 1}~{start + length} 章连续 {length} 章张力都在 2 以下,太平了")
    for start, length in _runs([not x for x in wins]):  # 太久没赢
        if length > 5:
            w.append(f"第 {start + 1}~{start + length} 章连续 {length} 章没有一次胜")
    for start, length in _runs([not g for g in gains]):  # 太久没变强
        if length > 10:
            w.append(f"第 {start + 1}~{start + length} 章连续 {length} 章没有力量上的所得")
    turns = [c.get("turn") or "无" for c in chapters]  # 反转太密,读者就什么都不信了
    big = [i for i, t in enumerate(turns) if t == "大"]
    for a, b in zip(big, big[1:]):
        if b - a < 8:
            w.append(f"第 {a + 1} 章和第 {b + 1} 章都是大反转,相隔不到 8 章,太密")
    for start, length in _runs([t in ("中", "大") for t in turns]):
        if length > 2:
            w.append(f"第 {start + 1}~{start + length} 章连续 {length} 章都有中等以上的反转,读者来不及信")
    if n >= 20:  # 一整批才要求的东西
        if not any(c["result"] == "负" and c["tension"] >= 4 for c in chapters):
            w.append("这一批里没有一次像样的失败(result=负 且 tension≥4)——有困难才有感动")
        if not any(c["mode"] == "情" and c["tension"] >= 4 for c in chapters):
            w.append("这一批里没有一章真到位的情感戏(mode=情 且 tension≥4)")
        if max(tension) < 5:
            w.append("这一批里没有一章张力到 5,缺一个最高点")
        if "笑" not in modes:
            w.append("这一批里没有一章以「笑」为主")
    if any(str(c.get("grip") or "").strip() for c in chapters):  # 只有这批有人标了档位才查松紧分布
        grips = [grip_of(c) for c in chapters]  # 没填的按"紧"算
        for start, length in _runs([g == "紧" for g in grips]):
            if length >= 4:
                w.append(f"第 {start + 1}~{start + length} 章连续 {length} 章都是「紧」,写作模型没有喘气的地方")
        if n >= 10:
            loose = sum(1 for g in grips if g == "松")
            if loose < n / 5:
                w.append(f"这一批 {n} 章里只有 {loose} 章是「松」,不到五分之一")
    return w


def main(argv: list[str] | None = None) -> int:
    """命令行入口:python -m huaben.rhythm stories/<书名>/vol-NN.json。只跑节奏检查,不查伏笔代号。"""
    path = (argv or sys.argv[1:])[0]
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    chapters = data if isinstance(data, list) else data.get("chapters") or []
    problems = rhythm_problems(chapters)
    for p in problems:
        print("错:" + p)
    if problems:
        return 1
    warnings = rhythm_warnings(chapters)
    for w in warnings:
        print("提醒:" + w)
    if not warnings:
        print("节奏检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
