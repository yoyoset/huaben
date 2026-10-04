# T032 剧本章纲:一章可以埋几条伏笔(或不埋);兑现、钩子、时间不再每章必填

依赖:T031(先合并 T031 再做这张,两张卡都动 `normalize.py` 和 `prompts.py`)。

## 为什么

用户 2026-10-05:

- "埋伏笔这个不要一刀切。没有硬性。自然要跟随剧情来起伏。"
- "章纲的兑现、钩子、时间,这些也是根据章的重要程度和兑现、钩子以及时间的重要程度来综合取舍。"

现状:

1. 剧本章纲的 `plant` 只能是一条。《阴差阳错》第 1 章本该埋四条(铜钱、师父叫什么、开场白、茶),只好摊到第 2、5、9 章去,
   埋的位置迁就了格式,而不是跟着剧情。
2. 导入章纲时 `when`、`payoff`、`hook` 每章必填(`script_import.check_volume_script`),一章过渡的日常也要硬编一条"兑现"。

**不变的原则**(T007,用户 2026-10-03 定的):伏笔是已经知道真相之后故意露出的一角——每一条都必须写得出 `truth`。放开的是"一章几条",不是"可以没有答案"。

## 已定的方案

### 1. `plant` 可以是一条,也可以是一个列表

- `huaben/planting.py` 加:

  ```python
  def normalize_plants(raw) -> list[dict]:
      """章纲里的 plant → 合法伏笔的列表。raw 是 dict → 当作一条;是 list → 逐条;别的 → []。
      每条走 normalize_plant,不合格的(缺 content 或 truth)丢掉。"""
  ```

- `huaben/pipeline/normalize.py` 的 `normalize_outline`:
  - 新增 `"plants": normalize_plants(d.get("plant"))`;
  - 原来的 `"plant"` 保留,值改为 `plants[0] if plants else None`(模型自己出章纲的那条路还在用单条的 `plant`,不动它)。
- `huaben/planting.py` 的 `to_register`:第一个参数从"一条或 None"改成**列表**(`plants: list[dict]`),逐条登记;
  欠账超限(非剧本书)时每条各记一行"未登记";返回值的形状不变。两处调用(`chapter.py` 第 129、184 行附近)改成传 `outline.get("plants") or []`。
  `chapter.py` 现在离 200 行上限很近:这两处只是换参数,不要加行。
- `huaben/pipeline/prompts.py` 的 `work_order`:
  - 有 `plants` 时:第一行 `本章要埋的伏笔(轻轻带一笔,不点破、不解释;各自放在剧情自然走到的地方,不要挤在一处):`,
    然后每条两行:`- <content>` 和 `  (它背后的真相,只给你知道,不要写进正文:<truth>)`,
    最后一行照旧 `除此之外,不要再留新的神秘物件、神秘人、神秘记号。`
  - 只有一条时也用这个新格式(不必保留旧的单条句式)。
  - 没有时照旧:`本章不埋新伏笔:不要留下来历不明的痕迹、记号、纸条或人影。`
- `huaben/script_import.py`:
  - `check_volume_script`:`plant` 是列表时逐条检查(`key`/`content`/`truth` 齐全、代号不重复——同一章里互相也不能重复);是 dict 时照旧。
    报错文字里带上是第几条:`第 N 章的第 K 条 plant 缺 key / content / truth`(只有一条且是 dict 时保持原文字)。
  - `_known_keys`:章纲的 `plant` 是列表时把每条的 `key` 都收进去。
- 入账那边(`ledger_messages`、`apply_ledger`)不改。

### 2. `when`、`payoff`、`hook` 不再必填

- `huaben/script_import.py` 的 `check_volume_script`:必填只剩 `title`、`outline`(把循环里的 `("title", "outline", "when", "payoff", "hook")` 改成 `("title", "outline")`)。
- `huaben/pipeline/prompts.py` 的 `work_order`:`结尾钩子:` 那一行只在 `outline.get("hook")` 非空时加(`when`、`payoff` 那两行本来就是非空才加)。
- `huaben/pipeline/prompts.py` 的 `write_messages`【必须】第 4 条 `结尾落在工单指定的钩子上。`:只在章纲有 `hook` 或 `ending` 时加;
  都没有时不加这一条(其余序号不用重排,少一条就少一条)。
- `huaben/rhythm.py` 的 `rhythm_warnings`,在"只有这一批标了 `grip` 才查"的那一段里加一条:
  档位是"紧"(含没填)的章,`payoff` 和 `hook` 都空 → `第 N 章是「紧」,却没写兑现也没写钩子`。
  (只是提醒。"中""松"章空着不提醒。)

改完每个 `.py` 仍须 ≤ 200 行。
**注意**:T031 合并后 `prompts.py` 199 行、`normalize.py` 198 行、`chapter.py` 198 行。这张卡要往前两个文件里加东西,先腾地方:
把 `prompts.py` 里的 `work_order` 整个函数挪到新模块 `huaben/pipeline/work_order.py`(`prompts.py` 里 `from .work_order import work_order  # noqa: F401` 保留旧路径);
`normalize.py` 里新加的东西尽量放在 `planting.py`。不要调高上限。

## 测试

1. `normalize_plants`:dict(合格)→ 一条;list 里两条合格一条缺 truth → 两条;`None`、`"x"`、`[]` → `[]`。
2. `normalize_outline`:`plant` 是两条的列表 → `plants` 两条、`plant` 等于第一条;`plant` 是 dict → `plants` 一条;没有 → `plants == []`、`plant is None`。
3. `to_register`:传两条(剧本书)→ 登记两条;传 `[]` → 不登记;非剧本书、欠账超限、传两条 → 不登记,运行记录里两条"未登记"。
   现有 `to_register` 的测试把单条参数改成单元素列表。
4. `work_order`:两条 `plants` → 两条的 content 和 truth 都在,含 `不要挤在一处`;没有 → 含 `本章不埋新伏笔`。`hook` 为空 → 不含 `结尾钩子`。
5. `check_volume_script`:章纲缺 `when`/`payoff`/`hook` → 不报;缺 `outline` → 仍报。
   `plant` 是两条的列表、代号各不相同 → 不报;两条同代号 → 报重复;第二条缺 truth → 报 `第 1 章的第 2 条 plant 缺`。
   后面的章 `foreshadows` 引用列表里第二条的代号 → 不报"还没埋下"。
6. 流水线:剧本书一章 `plant` 是两条的列表,写完后账本里多两条伏笔,`key` 各自对上。
7. `write_messages`:章纲没有 `hook` 也没有 `ending` → 【必须】里不含 `结尾落在工单指定的钩子上`;有 `hook` → 含。
8. `rhythm_warnings`:一批标了 `grip` 的章里,一章"紧"且 `payoff`、`hook` 都空 → 有那条提醒;同样情况的"松"章 → 没有。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数的变化。
2. `tests/test_structure.py` 通过。
3. 现有只带单条 `plant`(dict)的剧本文件(`stories/` 下的 json)用 `python -m huaben.rhythm <文件>` 检查,结果与改之前一样。

## 这次不做

- 不改模型自己出章纲的那条路(`PLANT_SCHEMA`、`PLANT_RULE` 的"最多一条"):生产上现在没有这种书。
- 不放开"伏笔必须有 truth"。
- 不部署,不碰生产,不改 `stories/`。
