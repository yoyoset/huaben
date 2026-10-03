# T007 伏笔:先知道答案再埋,不为埋而埋

## 为什么

2026-10-03 用户:"有时候很尬——为了埋伏笔而埋伏笔,这个伏笔完全毫无意义,很奇怪。能不能更专业一点。"

架构方查生产:

- 《算尽仙朝》13 章登记了 **29 条伏笔,一条都没收**;《杂役仙尊》14 章 23 条,只收了 1 条。平均每章新埋 2 条。
- 内容大量是这种:"枣树根旁湿土有两道浅浅鞋尖蹭印""破窗边青灰布条无风却晃动""铜钱边多了一道细刮痕,刮痕里嵌有青灰色粉末"。
- 它们的"回收计划"几乎全是一句套话:"后续章节揭示……身份,与……伏笔合并回收"。**没有一条写了答案是什么。**

原因有三个,都在流程里:

1. **伏笔不是计划出来的,是事后捡出来的。** 章纲里没有"本章埋什么"这一栏;是正文写完后,入账那一步让模型
   "登记本章新埋的伏笔"——于是正文里任何一个没解释的细节都被登记成伏笔,而写的时候根本没人知道它的答案。
2. **每章都要"结尾留钩子"**,最省事的钩子就是凭空冒出一个神秘物件/记号/纸条/人影——每章一个,就成了每章一条新"伏笔"。
3. **"欠账太多就不许再埋"只是章纲提示里的一句话**,而登记发生在入账,程序上没有任何限制,所以 29 条照埋不误。

专业的做法:伏笔是作者**已经知道真相**之后,故意提前露出的一角。不知道答案的"神秘细节"不是伏笔,是欠读者的账。

## 已定的方案

1. 章纲多一栏 `plant`:本章要埋的伏笔,**最多一条,多数章是 null**;必须同时写出它背后的真相(`truth`)。
2. **登记伏笔以章纲的 `plant` 为准,不再以入账捡出来的为准。** 入账里的 `foreshadows_new` 不再登记进账本,
   只作为"作者计划外留下的悬念"写一条运行记录(留痕,方便以后看作者是不是还在乱留)。
3. 未回收的伏笔总数超过上限时,程序直接不登记新的(哪怕章纲给了 `plant`),并留痕。
4. 结尾钩子的要求改成"用已有的东西",不许为了钩子新造神秘物。

## 改哪些文件

### 1. 新建 `huaben/planting.py`(纯函数与常量,照抄)

文件头 docstring 自己写:把"为什么"里的实测数字和三个原因写进去。

```python
from .foreshadow_scale import normalize_scale

OPEN_TOTAL_LIMIT = 12  # 未回收伏笔(不分大小)超过这个数:先还账,一条新的都不登记

PLANT_SCHEMA = ('  "plant": {"content": "本章要埋的伏笔:读者会看到什么", '
                '"truth": "它背后的真相是什么、将来怎么改变剧情(你必须现在就知道答案;只有编辑和作者知道,不写进正文)", '
                '"scale": "short / medium / long / epic"},')

PLANT_RULE = ("伏笔是你已经知道真相之后,故意提前露出的一角——不知道答案的神秘细节不是伏笔,是欠读者的账。"
              "plant 最多一条,多数章应为 null;只有当你说得出它背后的真相(truth),而且这个真相会改变后面的剧情时才埋。"
              "优先埋卷计划里【本卷要埋的伏笔】列出的那些。不要埋:来历不明的痕迹、记号、粉末、布条、脚印、"
              "又一张纸条、一闪而过的人影——除非你现在就能在 truth 里写出它是谁留的、为什么。")

HOOK_RULE = ("结尾钩子用已有的东西:本章冲突的后果、已有伏笔往前走了一步、马上要来的危险或抉择。"
             "不要为了钩子新造一个神秘物件、神秘人或神秘记号。")

NO_PLANT_RULE = "未回收的伏笔已有 {n} 条(上限 {limit}):本章 plant 必须为 null,把篇幅用在回收和推进已有的伏笔上。"


def normalize_plant(raw) -> dict | None:
    """章纲里的 plant → 合法形状;缺 content 或 truth 就是 None(说不出真相的不算伏笔)。"""
    if not isinstance(raw, dict):
        return None
    content, truth = str(raw.get("content") or "").strip(), str(raw.get("truth") or "").strip()
    if not content or not truth:
        return None
    return {"content": content, "truth": truth, "scale": normalize_scale(raw.get("scale"))}


def plant_rule(open_count: int) -> str:
    """章纲提示里的伏笔要求:欠账超限时改成"本章不许埋"。"""
    if open_count > OPEN_TOTAL_LIMIT:
        return NO_PLANT_RULE.format(n=open_count, limit=OPEN_TOTAL_LIMIT)
    return PLANT_RULE


def to_register(plant: dict | None, open_count: int, extracted: list[dict]) -> tuple[list[dict], list[str]]:
    """→ (要登记进账本的新伏笔, 运行记录)。只登记章纲计划的那一条;入账捡出来的(extracted)一律不登记、只留痕。"""
    notes = [f"计划外的悬念(未登记为伏笔):{f['content'][:60]}" for f in extracted]
    if plant is None:
        return [], notes
    if open_count > OPEN_TOTAL_LIMIT:
        return [], notes + [f"未回收伏笔 {open_count} 条超过上限 {OPEN_TOTAL_LIMIT},章纲计划的伏笔未登记:{plant['content'][:60]}"]
    return [{"content": plant["content"], "payoff_plan": plant["truth"], "scale": plant["scale"]}], notes
```

### 2. `huaben/pipeline/normalize.py` 的 `normalize_outline`

返回的字典里加一项:`"plant": normalize_plant(d.get("plant")),`。`normalize.py` 现在 179 行(T006 之后 180),
加完 import 可能到 182,够用;超 200 就把 `normalize_outline` 搬到新文件 `huaben/pipeline/normalize_outline.py`,
并保证原来 `from .normalize import normalize_outline` 的地方仍然能导入。

### 3. `huaben/pipeline/prompts.py`

- `OUTLINE_SCHEMA`:在 `"foreshadows"` 那一行**后面**插入 `PLANT_SCHEMA` 的内容。
- `outline_messages`:
  - 把那句 `"伏笔该推进的推进、该收的收;结尾留钩子;"` 里的 `结尾留钩子;` 删掉(钩子的要求改由 `HOOK_RULE` 给)。
  - 在 `{planting_rule(...)}\n` 后面加 `{plant_rule(len(ctx.foreshadows))}\n{HOOK_RULE}\n`。
- `work_order`:在"本章要推进或回收的伏笔"那一段之后加(`outline.get("plant")` 非空时):
  ```
  本章要埋的伏笔(轻轻带一笔,不点破、不解释):{content}
  (它背后的真相,只给你知道,不要写进正文:{truth})
  除此之外,不要再留新的神秘物件、神秘人、神秘记号。
  ```
  `plant` 为空时加一行:`本章不埋新伏笔:不要留下来历不明的痕迹、记号、纸条或人影。`
- `prompts.py` 超 200 行的处理办法同 T006(把 `recent_hooks` 搬去 `rules.py`;还不够就把 `work_order` 搬到新文件 `huaben/pipeline/work_order.py`)。

### 4. `huaben/pipeline/chapter.py`

在调用 `apply_ledger(...)` **之前**加:

```python
ledger["foreshadows_new"], plant_notes = to_register(outline.get("plant"), len(ctx.foreshadows), ledger["foreshadows_new"])
```

并把 `plant_notes` 和其它警告一样写运行记录(`repo.log_run(conn, book_id, "ledger", chapter_idx=idx, note=w)`)。
`ledger_apply.py` 不用改(它照旧登记 `ledger["foreshadows_new"]`,只是现在里面最多一条、且来自章纲)。

### 5. 不要动

- `LEDGER_SCHEMA` 和 `ledger_messages`(入账照旧抽 `foreshadows_new`,现在只用来留痕)。
- `foreshadow_scale.py` 的 `planting_rule` 与 `OPEN_LIMIT`(到期回收的逻辑照旧)。

### 6. 测试(新建 `tests/test_planting.py`)

| 测试 | 期望 |
|---|---|
| `normalize_plant({"content":"a","truth":"b","scale":"长线"})` | `{"content":"a","truth":"b","scale":"long"}` |
| `normalize_plant({"content":"a","truth":""})` | `None` |
| `normalize_plant(None)`、`normalize_plant("x")` | `None` |
| `to_register(None, 3, [{"content":"脚印"}])` | `([], [含"计划外的悬念"和"脚印"的一条])` |
| `to_register(plant, 3, [])` | 登记 1 条,`payoff_plan == plant["truth"]`,记录为空 |
| `to_register(plant, 13, [])` | 登记 0 条,记录里含"超过上限" |
| `plant_rule(12)` | 等于 `PLANT_RULE` |
| `plant_rule(13)` | 含"必须为 null" |

另外:

- `outline_messages` 输出含 `HOOK_RULE`、含 `PLANT_RULE`(未回收 ≤12 时);不再含"结尾留钩子;"。
- `work_order`:有 `plant` → 含"本章要埋的伏笔"和 truth 文字;无 → 含"本章不埋新伏笔"。
- 端到端(照 `tests/test_pipeline.py` 里现有写法,剧本 LLM):章纲带 `plant`、入账带两条 `foreshadows_new` →
  定稿后账本里**只新增 1 条**伏笔,内容是章纲 `plant.content`,`payoff_plan` 是 `truth`;运行记录里有两条"计划外的悬念"。
- 章纲不带 `plant`、入账带一条 `foreshadows_new` → 账本新增 0 条。
- 现有测试里凡是依赖"入账的 foreshadows_new 会进账本"的,改成在章纲里给 `plant`(这是本卡有意改变的行为;改了哪些测试在报告里逐个列出,**不要删测试**)。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化、改了哪些旧测试及原因。
2. `tests/test_structure.py` 通过。
3. 报告里贴出 `to_register` 三种情况的真实输出(python -c 打印)。

## 这次不做

- 不清理已经登记的旧伏笔(那是 T008)。在 T008 之前,生产两本书未回收数都超过 12,效果就是"暂时一条新的都不埋"——这是想要的。
- 不改卷规划(卷的 `plant` 列表照旧)。
- 不部署、不在生产上试。

## 审核记录

(架构方填)
