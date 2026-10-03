# T003 节奏:每个节拍给不同的章数(该快的快、该慢的慢)

## 为什么

2026-10-03 用户:"都四章了,连山门都还没进";但也不能一说快就章章都快——要有快有慢,由故事情节决定。

架构方查了生产数据,原因在 `huaben/pipeline/rules.py` 的 `pacing_rule`:

```python
i = min(len(beats), ctx.volume_done * len(beats) // target + 1)
```

**本章该写哪个节拍,是用"已写章数 ÷ 总章数"平均摊出来的**——每个节拍不管轻重都拿到同样多的章。实际后果:

- 《算尽仙朝》32 章 / 10 个节拍 = 每个节拍 3.2 章。第 1 个节拍只是"镇上算账、决定去考"这种开场过渡,
  也被摊了 3 章,所以第 1~3 章还在镇上和路上,第 4 章才到山门口核验户籍,第 5 章才进考场。
- 《杂役仙尊》30 章 / 11 个节拍。第 5 个节拍"偷学功法被撞破"是一场小戏,被摊了 3 章,
  于是第 12、13、14 章把"划字练气、被沈青梧撞破、重申互不揭发"原样演了三遍。

所以"慢"和"重演"是同一个病:**小节拍被硬撑成好几章**。反过来只在写法设定里选"快",也只是让每一章都赶,
重头戏同样被压扁。真正要的是**章数按节拍的分量分配**。

## 已定的方案

1. 卷规划时,编辑除了给节拍,还给**每个节拍几章**(`beat_chapters`,与 `beats` 等长的整数列表)。
   过渡 1 章,重头戏 3~5 章。卷的总章数 = 这些数之和。
2. 写每一章时,按这份预算算出"现在在第几个节拍、是它的第几章、它一共几章",据此给编辑和作者不同的节奏要求。
   这是**程序算的**(纯函数),不让模型判断"这个节拍写完没有"。
3. 旧卷没有预算(空列表)→ 走原来的平均算法,行为不变。给旧卷补预算是 T004。

## 改哪些文件

### 1. 新建 `huaben/beat_budget.py`(纯函数,照抄,不要改逻辑)

文件头 docstring 自己写:把上面"为什么"里的公式和两本书的实测写进去。

```python
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
    return (f"节奏:{head}是重头戏,共 {n} 章,本章是第 {k} 章——慢下来把这场戏写足;"
            f"但本章必须有一个上一章没有的实质进展(局面、信息或关系变了),不要把上一章的事再演一遍。")
```

### 2. 数据库:`volumes.beat_chapters`

- `huaben/migrations.py` 末尾加第 18 条迁移(注释照前面几条的写法,写清日期和原因):
  `"ALTER TABLE volumes ADD COLUMN beat_chapters TEXT NOT NULL DEFAULT '[]';"`
- 其它要同步的地方,**照第 13 条迁移(`volumes.arc`)当时的做法**:在仓库里搜 `arc`,看 `schema.py`、`repo/volumes.py`、
  `tests/test_migrate.py` 当时各改了什么,`beat_chapters` 同样处理。
- `huaben/repo/volumes.py`:`create_volume` 加参数 `beat_chapters=None`(存 `dumps(beat_chapters or [])`);
  `_vol` 的 `loads` 列表里加 `"beat_chapters"`。

### 3. 卷规划

- `huaben/pipeline/volume_prompts.py`:
  - `PLAN_SCHEMA` 里 `"beats"` 那一行下面加一行:
    `  "beat_chapters": [每个节拍给几章(整数),与 beats 一一对应、等长,不要平均分],`
  - `plan_messages` 的 user 文本里,在 `{ARC_RULE}\n` 这一行**之前**加 `{BUDGET_RULE}\n`(从 `..beat_budget` 导入)。
- `huaben/pipeline/parsing.py` 的 `parse_volume_plan`:算完 `d["beats"]` 之后加
  ```python
  d["beat_chapters"] = normalize_budget(d.get("beat_chapters"), len(d["beats"]))
  ```
  并且:如果 `d["beat_chapters"]` 不是 None,且它的和在 5~200 之间,就让 `d["target_chapters"] = sum(d["beat_chapters"])`
  (覆盖模型另给的数;和越界时把 `d["beat_chapters"]` 置为 None,`target_chapters` 走原逻辑)。
- `huaben/pipeline/volume.py` 的 `plan_volume`:`repo.create_volume(...)` 多传 `beat_chapters=plan["beat_chapters"]`。

### 4. 写章时用预算

`huaben/pipeline/rules.py` 的 `pacing_rule`:

- 计算 `i` 的那一行换成:
  ```python
  budget = v.get("beat_chapters") or []
  if beats and len(budget) == len(beats):
      i, k, n = locate(budget, ctx.volume_done)
  else:
      i, k, n = (min(len(beats), ctx.volume_done * len(beats) // target + 1) if beats else 0), 0, 0
  ```
- `elif beats:` 分支里的 `base = ...` 换成 `base = beat_line(beats, i, k, n)`。
- "最后一章""收尾阶段"两个分支和 `arc_pacing(...)` 那一行**不要动**。

`huaben/pipeline/prompts.py` 的 `write_messages`:`parts` 列表里,在 `work_order(...)` 那一项**后面**加一项 `pacing_rule(ctx)`
(作者现在看不到节奏要求,只有编辑看得到;作者不知道"这章是过渡要快写",就会把过渡也写成一场场戏)。

### 5. 写法设定里"节奏"三个选项的说明

`huaben/craft.py` 的 `"pacing"`,三条说明整体替换为(一字不改):

```python
"fast": ("快", "整体偏快:过渡(赶路、手续、日常)一律几句话带过,每章至少一个爽点或反转;"
               "但重头戏照样写足——快是不拖,不是每场戏都赶"),
"balanced": ("张弛有度", "该快的快、该慢的慢:过渡一笔带过,重头戏慢下来写足;紧张与舒缓交替,高潮前有铺垫"),
"slow": ("慢热", "重氛围与人物塑造,冲突逐步升级;慢的是重头戏里的细节与情绪,过渡和流程照样不拖"),
```

### 6. 测试

新建 `tests/test_beat_budget.py`:

| 测试 | 期望 |
|---|---|
| `locate([1,3,2], 0)` | `(1,1,1)` |
| `locate([1,3,2], 1)` | `(2,1,3)` |
| `locate([1,3,2], 3)` | `(2,3,3)` |
| `locate([1,3,2], 4)` | `(3,1,2)` |
| `locate([1,3,2], 6)`(写超了) | `(3,2,2)` |
| `locate([0,2,3], 0)`(跳过 0) | `(2,1,2)` |
| `normalize_budget([1,3,2], 3)` | `[1,3,2]` |
| `normalize_budget([1,3], 3)`(长度不对) | `None` |
| `normalize_budget([1,"3",2], 3)` | `None` |
| `normalize_budget([0,20,2], 3)`(夹到 1..8) | `[1,8,2]` |
| `normalize_budget(None, 3)` | `None` |
| `beat_line(["a","b"], 1, 1, 1)` | 含"只给 1 章"和"「b」" |
| `beat_line(["a","b"], 2, 3, 3)` | 含"最后一章"和"本卷的收尾" |
| `beat_line(["a","b"], 1, 1, 3)` | 含"重头戏"和"第 1 章" |
| `beat_line(["a","b"], 1, 0, 0)` | 含"大约应推进" |

另外在现有测试文件里加(放不下 200 行就新建文件):

- `parse_volume_plan`:给了合法 `beat_chapters` → `target_chapters` 等于它的和;长度对不上 → `beat_chapters` 为 None、不报错。
- 卷规划提示里含 `BUDGET_RULE` 的原文。
- 有预算的卷:章纲提示(`outline_messages`)和正文提示(`write_messages`)里都出现 `beat_line` 的那一句;
  没预算的旧卷:出现"大约应推进"(行为不变)。
- 迁移:照 `tests/test_migrate.py` 里已有的写法,验证旧库升级后 `volumes` 有 `beat_chapters` 列、默认 `[]`。

改了 `craft.py` 的文字后,如果有旧测试断言了原来的句子,把断言改成新句子(这是唯一允许改旧断言的地方,改了哪几处在报告里列出)。

## 验收标准

1. `python -m pytest -q` 全过;报告里写清测试总数从多少变成多少。
2. `tests/test_structure.py` 通过(单文件 ≤200 行、SQL 只在 repo/)。
3. 下面命令输出三行,分别含"只给 1 章""重头戏""最后一章":
   ```bash
   python -c "from huaben.beat_budget import locate, beat_line; b=['镇上算账','考场策论','外门杂役']; g=[1,3,2]; [print(beat_line(b,*locate(g,d))) for d in (0,1,3)]"
   ```
4. 没有改动卡里没点名的提示词文字。

## 这次不做

- 不给已经在写的旧卷补预算(T004)。
- 不让模型判断"节拍写完没有"——位置完全由预算和已写章数算出。先看这个简单办法够不够,不够再加。
- 不改前端。
- 不部署、不在生产上试(架构方验收时做:在生产库副本上规划一卷,看预算是不是真的不平均)。

## 审核记录

**通过(2026-10-03)**。架构方重跑:401 项全过;`beat_budget.py` 与卡里参考实现逐项比对一致;已部署(生产迁移 v18)。
生产库副本实测(真模型各规划一卷,用完即删副本):
- 《杂役仙尊》第 2 卷:20 个节拍,预算 `[1,2,2,2,1,2,1,2,3,2,1,2,2,3,3,2,1,3,3,2]` 共 40 章——过渡(搬入弟子院、发现残页、套话)给 1 章,当众对质、下井、大会摊牌给 3 章。符合预期。
- 《算尽仙朝》第 2 卷:10 个节拍,预算 `[2,3,2,4,3,2,4,3,4,3]` 共 30 章——有轻重(谷底与设局 4 章),但**没有 1 章的过渡**;原因是它规划的 10 个节拍本身都是事件、没有纯过渡。先观察,不改。
已知:《杂役仙尊》给了 20 个节拍(schema 写的是 5~10),旧有的宽松,不是本卡引入的。
