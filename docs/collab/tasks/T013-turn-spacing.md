# T013 节奏检查加一栏:反转的大小与间隔

依赖:T012 通过(已通过)。

## 为什么

2026-10-03 用户:"反转应该跟节奏一样,有节奏,不要刻意。"反转太密,读者就什么都不信了(`docs/story-craft.md` 第七章 5、第一章 3)。
T012 的节奏检查里没有反转这一条线。本卡给章纲加一栏 `turn`,只查"太密",**不查"必须有几个"**——密度数字是报警线,不是要凑满的定额。

## 改哪些文件

### `huaben/rhythm.py`

1. 常量加一行:`TURNS = ("无", "小", "中", "大")`。
2. `rhythm_problems` 的循环里加(放在 `result` 的检查后面):
   ```python
           if (ch.get("turn") or "无") not in TURNS:
               problems.append(f"第 {n} 章 turn 必须是 {'/'.join(TURNS)} 之一(可不填)")
   ```
3. `rhythm_warnings` 里,在 `if n >= 20:` **之前**加:
   ```python
       turns = [c.get("turn") or "无" for c in chapters]  # 反转太密,读者就什么都不信了
       big = [i for i, t in enumerate(turns) if t == "大"]
       for a, b in zip(big, big[1:]):
           if b - a < 8:
               w.append(f"第 {a + 1} 章和第 {b + 1} 章都是大反转,相隔不到 8 章,太密")
       for start, length in _runs([t in ("中", "大") for t in turns]):
           if length > 2:
               w.append(f"第 {start + 1}~{start + length} 章连续 {length} 章都有中等以上的反转,读者来不及信")
   ```

`turn` 的含义(写进文件头 docstring):这一章的反转有多大。`小` = 局面/信息/关系变了一下;`中` = 一个目标、一个局、一份代价翻了;
`大` = 改变读者对一个人或一件事的整体看法。可以不填,不填当 `无`。

### 测试(加在 `tests/test_rhythm.py`;超 200 行就新建 `tests/test_rhythm_turn.py`)

- 第 3 章和第 9 章都是 `大` → 提醒里有"太密";第 3 章和第 12 章 → 没有。
- 连续 3 章 `turn` 为 中/大/中 → 提醒里有"来不及信";连续 2 章 → 没有。
- `turn="巨"` → `rhythm_problems` 报一条;不填 `turn` → 不报。
- 原有的 30 章"排好的章纲"用例仍然返回 `[]`。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化。
2. 报告里贴出对一份"第 2、5 章都是大反转"的 6 章临时文件运行 `python -m huaben.rhythm` 的输出。

## 这次不做

- 不查"一批里必须有几个反转"。
- 不查伏笔、情感债的间隔(那些跨批次,由架构方对着总谱人工核)。

## 审核记录

(架构方填)
