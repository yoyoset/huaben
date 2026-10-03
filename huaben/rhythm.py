"""节奏检查:章纲带四个标记(mode/tension/result/gain),导入时把不合拍的地方列出来。

为什么(2026-10-03 用户:"所有都应该有节奏。进度有节奏,力量路线有节奏,剧情起伏也应该有节奏。有困难才有感动。"):
节奏的规矩写在 `docs/story-craft.md` 第五节(口味轮换、压与放、胜负密度、力量所得的间隔),但规矩只写在文档里就只能靠写章纲的人自觉——
此前"四章没进山门""连续三章重演同一场戏"都是没人检查节奏的结果。
检查结果是**提醒**,不是拦截:有的不合拍是有意的(比如决战连打五章),由导入的人决定改不改。
"""
import json
import sys
from pathlib import Path

MODES = ("战", "笑", "情", "谜", "修")
RESULTS = ("胜", "负", "平", "无")


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
    if n >= 20:  # 一整批才要求的东西
        if not any(c["result"] == "负" and c["tension"] >= 4 for c in chapters):
            w.append("这一批里没有一次像样的失败(result=负 且 tension≥4)——有困难才有感动")
        if not any(c["mode"] == "情" and c["tension"] >= 4 for c in chapters):
            w.append("这一批里没有一章真到位的情感戏(mode=情 且 tension≥4)")
        if max(tension) < 5:
            w.append("这一批里没有一章张力到 5,缺一个最高点")
        if "笑" not in modes:
            w.append("这一批里没有一章以「笑」为主")
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
