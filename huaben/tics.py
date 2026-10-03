"""口头禅统计:一张"哪一章、哪种写法、多少处"的表。只读,不改正文。

为什么(T025,2026-10-04):《弄假成真》第 3~30 章回看时发现"一动不动""一级一级 / 一滴一滴"这类写法
后半段很密(第 30 章叠用 21 处)。接句工具只动标点,管不了这个;架构方手改之前先要一张表。
纯统计,不接进写章流程,不做打回。
"""
import re
import sys
from collections import Counter
from pathlib import Path

FIXED = ("一动不动", "慢慢", "一点一点", "一字一字", "没有说话", "没说话", "很久")
REDUP = re.compile(r"一(.)[，、]?一\1")
REDUP_LIMIT = 2.0


def tic_counts(text: str) -> dict:
    """返回叠用处数、每千字叠用、固定说法次数、最多的 3 种叠用。"""
    chars = len(re.sub(r"\s", "", text))
    redups = [m.group(0).replace("，", "").replace("、", "") for m in REDUP.finditer(text)]
    fixed = {p: text.count(p) for p in FIXED if p in text}
    top = [(p, c) for p, c in Counter(redups).most_common(3)]
    return {"chars": chars, "redup": len(redups),
            "redup_per_k": round(len(redups) / chars * 1000, 1) if chars else 0.0,
            "fixed": fixed, "top_redup": top}


def tic_report(chapters: dict[int, str]) -> list[str]:
    """{章号: 正文} → 每章一行的文字报告,按章号排序;最后一行是合计。"""
    lines, dense, total = [], [], 0
    for n in sorted(chapters):
        r = tic_counts(chapters[n])
        total += r["redup"]
        mark = "【密】" if r["redup_per_k"] > REDUP_LIMIT else ""
        if mark:
            dense.append(n)
        top = "、".join(f"{p}×{c}" for p, c in r["top_redup"]) or "无"
        fixed = "、".join(f"{p}×{c}" for p, c in r["fixed"].items()) or "无"
        lines.append(f"第{n:02d}章 叠用 {r['redup']} 处（每千字 {r['redup_per_k']}）{mark} 最多:{top} 固定说法:{fixed}")
    dense_text = "、".join(f"{n:02d}" for n in dense) if dense else "无"
    lines.append(f"合计 叠用 {total} 处;超过每千字 {REDUP_LIMIT} 的章:{dense_text}")
    return lines


def main(argv: list[str] | None = None) -> int:
    """命令行入口:python -m huaben.tics <目录>。读目录下的 NN.txt(UTF-8),打印报告。"""
    sys.stdout.reconfigure(encoding="utf-8")
    d = Path((argv or sys.argv[1:])[0])
    files = sorted(d.glob("[0-9][0-9].txt")) if d.is_dir() else []
    if not files:
        print(f"目录不存在或里面没有 NN.txt:{d}")
        return 1
    chapters = {int(p.stem): p.read_text(encoding="utf-8") for p in files}
    for line in tic_report(chapters):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
