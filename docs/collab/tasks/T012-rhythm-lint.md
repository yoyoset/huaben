# T012 剧本制(三):章纲带节奏标记,导入时检查节奏

依赖:T011 通过。

## 为什么

2026-10-03 用户:"所有都应该有节奏。进度有节奏,力量路线有节奏,剧情起伏也应该有节奏。有困难才有感动。"
节奏的规矩写在 `docs/story-craft.md` 第五节(口味轮换、压与放、胜负密度、力量所得的间隔)。但规矩只写在文档里,就只能靠写章纲的人自觉——
此前"四章没进山门""连续三章重演同一场戏"都是没人检查节奏的结果。本卡让每章章纲带上四个标记,导入时由程序把不合拍的地方列出来。

检查结果是**提醒**,不是拦截:有的不合拍是有意的(比如决战连打五章)。提醒要一条条列给导入的人看,由他决定改不改。

## 已定的方案

### 1. 章纲多四栏(只有剧本章纲用;模型出的章纲不要求)

| 栏 | 取值 | 意思 |
|---|---|---|
| `mode` | `战` / `笑` / `情` / `谜` / `修` 之一 | 这一章的主要口味 |
| `tension` | 1~5 的整数 | 张力:1 喘气的日常,3 有事在推进,5 生死关头或最大的揭示 |
| `result` | `胜` / `负` / `平` / `无` | 这一章主角一方的胜负;没有较量就是"无" |
| `gain` | 文字,可空 | 力量上的所得:学会什么、升到哪、得到什么(没有就空着) |

这四栏不进给写作模型的工单(它们是给检查用的),但要原样存进 `scripted_outlines`。
`normalize_outline` 不认识它们会丢掉——所以**检查在存库之前、对原始章纲做**,不要改 `normalize_outline`。

### 2. 新建 `huaben/rhythm.py`(纯函数,照抄)

文件头 docstring 自己写:引用上面"为什么"和 `docs/story-craft.md` 第五节。

```python
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
```

### 3. 接进导入(`huaben/script_import.py`)

- `check_volume_script` 的末尾加:`problems += rhythm_problems(chapters)`。
- `import_volume`:检查通过后,算 `warnings = rhythm_warnings(chapters)`,放进返回值:`{"volume_idx":…, "chapters":[…], "rhythm_warnings": [...]}`。
- 接口加一个只检查不导入的开关:`POST /api/books/{book_id}/import/volume?dry_run=1` → 只返回 `{"problems": [...], "rhythm_warnings": [...]}`,**什么都不写库**
  (问题非空时仍返回 200,因为这次调用的目的就是看问题)。架构方写完一批章纲先用它过一遍。
- 另加一个不需要服务器的命令行入口,方便在开发机上直接检查文件:
  `python -m huaben.rhythm stories/某书/vol-01-a.json` → 逐行打印 problems(前缀 `错:`)和 warnings(前缀 `提醒:`),没有就打印 `节奏检查通过`。
  (这个入口只跑 `rhythm_problems` 和 `rhythm_warnings`,不查伏笔代号——那要数据库。)

### 4. 测试(新建 `tests/test_rhythm.py`)

造章纲用一个小帮手:`ch(mode="战", tension=3, result="无", gain="")`。

- `rhythm_problems`:合法 → `[]`;`mode="打"`、`tension=6`、`tension=True`、`result="赢"`、缺栏 —— 各报一条。
- `rhythm_warnings`,每条规则一正一反:
  - 4 章连续"笑" → 提醒;3 章 → 不提醒。6 章连续"战" → 提醒;5 章 → 不提醒。
  - 5 章连续 tension 4 → 提醒;4 章 → 不提醒。4 章连续 tension 2 → 提醒;3 章 → 不提醒。
  - 6 章没有"胜" → 提醒;5 章 → 不提醒。11 章没有 gain → 提醒;10 章 → 不提醒。
  - 20 章、没有"负且 tension≥4" → 提醒;19 章同样情况 → 不提醒(不到一整批不要求)。
  - 一份 30 章、精心排好的章纲(自己在测试里造:口味轮换、每 3 章一胜、第 20 章 负/5、第 21 章 情/4、每 8 章一个 gain、有"笑")→ `[]`。
- `import_volume` 的返回值里有 `rhythm_warnings`;`dry_run=1` 不写库(卷数、`scripted_outlines` 行数前后不变)。
- 命令行入口:对一个临时文件运行,断言输出里有 `提醒:` 或 `节奏检查通过`。
- T011 的现有测试里,剧本章纲都要补上这四栏才能过检查——**补栏,不要删断言**;改了哪些在报告里列出。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化。
2. `tests/test_structure.py` 通过。
3. 报告里贴出命令行入口对一份故意排得很差的 6 章章纲(自己造一个临时文件)的完整输出。

## 这次不做

- 不把提醒变成拦截。
- 不检查模型出的章纲(非剧本书)。
- 不做前端展示。

## 审核记录

**通过(2026-10-03)**。461 项全过;`rhythm.py` 与卡一致;已部署。
**流程提醒**:本卡依赖的 T011 当时还在「待审」就开工了(报告里写了是用户直接指示)。这次结果没问题,但规则不变——依赖没「通过」不开工;
用户让你继续时,若只剩依赖未通过的卡,照实说"要等架构方验收"。反转间隔的检查另出 T013。
