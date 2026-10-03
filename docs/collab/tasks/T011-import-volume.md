# T011 剧本制(二):导入卷剧本,按写好的章纲写章

依赖:T010 通过。

## 为什么

见 `docs/architecture.md` 第 5.5 节。卷规划和本卷每一章的章纲由架构方事先写好(`stories/<书名>/vol-NN.json`),
flash 只照着写正文。本卡做三件事:导入卷剧本;写章时用导入的章纲而不是让模型现出;用"伏笔代号"让章纲之间能互相引用伏笔。

## 已定的方案

### 1. 数据库(迁移 20)

```sql
CREATE TABLE scripted_outlines (
  book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL,              -- 全书章序号
  outline TEXT NOT NULL,             -- JSON,章纲
  PRIMARY KEY(book_id, idx)
);
ALTER TABLE ledger_foreshadows ADD COLUMN key TEXT NOT NULL DEFAULT '';
```

`key` = 伏笔代号(如 `"F3"`),只有剧本书的伏笔有。为什么需要:章纲是提前写好的,而伏笔的数据库编号要等写到埋它的那一章才产生,
所以章纲里只能用代号说"本章回收 F3"。

SQL 放进 `huaben/repo/`(新文件 `repo/scripts.py`):`save_scripted_outlines(conn, book_id, {idx: outline_dict})`、
`get_scripted_outline(conn, book_id, idx) -> dict | None`、`foreshadow_ids_by_key(conn, book_id) -> dict[str, int]`;
`add_foreshadow` 多一个参数 `key=""`。

### 2. 卷剧本的格式(`vol-NN.json`,也是接口的请求体)

```json
{
  "volume": {
    "goal": "...", "beats": ["..."], "beat_chapters": [1, 3, 2],
    "plant": ["..."], "resolve": [],
    "arc": { 与 huaben/arc.py 的 ARC_SCHEMA 相同 }
  },
  "chapters": [
    {
      "title": "...", "outline": "...", "when": "...", "characters": ["..."],
      "foreshadows": ["F1"],
      "plant": {"key": "F2", "content": "...", "truth": "...", "scale": "long"},
      "planned_reversals": [], "payoff": "...", "novelty": "...", "hook": "..."
    }
  ]
}
```

### 3. 新增到 `huaben/script_import.py`

纯函数(照抄):

```python
def check_volume_script(data: dict, known_keys: set[str]) -> list[str]:
    """卷剧本的硬性检查,返回问题列表(空 = 合格)。known_keys:这本书此前已经埋下的伏笔代号。"""
    problems = []
    vol, chapters = data.get("volume") or {}, data.get("chapters") or []
    beats, budget = vol.get("beats") or [], vol.get("beat_chapters") or []
    if not str(vol.get("goal") or "").strip():
        problems.append("volume.goal 为空")
    if not beats or len(budget) != len(beats) or any(not isinstance(n, int) or n < 1 for n in budget):
        problems.append("beat_chapters 必须与 beats 等长,且每项是 ≥1 的整数")
    elif len(chapters) != sum(budget):
        problems.append(f"章纲有 {len(chapters)} 章,但 beat_chapters 之和是 {sum(budget)}")
    keys = set(known_keys)
    for n, ch in enumerate(chapters, 1):
        for field in ("title", "outline", "when", "payoff", "hook"):
            if not str(ch.get(field) or "").strip():
                problems.append(f"第 {n} 章缺 {field}")
        for k in ch.get("foreshadows") or []:
            if k not in keys:
                problems.append(f"第 {n} 章引用了还没埋下的伏笔代号 {k!r}")
        plant = ch.get("plant")
        if plant:
            k = str(plant.get("key") or "").strip()
            if not k or not str(plant.get("content") or "").strip() or not str(plant.get("truth") or "").strip():
                problems.append(f"第 {n} 章的 plant 缺 key / content / truth")
            elif k in keys:
                problems.append(f"第 {n} 章的伏笔代号 {k!r} 重复")
            keys.add(k)
    titles = [str(ch.get("title") or "").strip() for ch in chapters]
    problems += [f"章节标题重复:{t}" for t in sorted({t for t in titles if t and titles.count(t) > 1})]
    return problems
```

`import_volume(conn, llm, settings, book_id, data) -> dict`:

1. 书必须存在且 `scripted=1`,否则报错。
2. 有进行中的卷:已写满(定稿章数 ≥ 计划章数)就先 `seal_volume`(照 `ensure_active_volume` 里的写法);没写满 → 报错"当前这一卷还没写完"。
3. `check_volume_script(data, 这本书已有的伏笔代号)` 有问题 → 报错,把全部问题一起返回。
4. 建卷:`status="active"`,`target_chapters = sum(beat_chapters)`,`arc` 过 `normalize_arc`;
   `resolve` 里的代号翻译成编号(用 `foreshadow_ids_by_key`;翻译不了的报错)。
5. 章纲按顺序存进 `scripted_outlines`,章序号从"下一章的序号"(`repo.next_chapter_idx`)起连续编。原样存(含 `plant.key`、代号形式的 `foreshadows`)。
6. 清掉 `books.gen_error`。返回 `{"volume_idx": N, "chapters": [起始章号, 结束章号]}`。

第 4~6 步在一个事务里。

### 4. 写章时用导入的章纲

`huaben/pipeline/chapter.py` 的 `_outline`:开头先查 `repo.get_scripted_outline(conn, book_id, idx)`:

- 有:不调模型。把章纲里代号形式的 `foreshadows` 翻译成编号(翻译不了的丢掉并写一条运行记录),然后过 `normalize_outline`;
  写一条运行记录 `outline: 来自剧本`;照旧 `create_chapter`。
- 没有、且这本书 `scripted=1`:抛 `ChapterFailed("这一章没有剧本章纲", step="script", idx=idx)`(不许退回让模型出章纲)。
- 没有、且不是剧本书:走原来的路,行为不变。

翻译代号的纯函数放 `script_import.py`:

```python
def resolve_keys(outline: dict, ids_by_key: dict[str, int]) -> tuple[dict, list[str]]:
    """章纲里 foreshadows 的代号 → 数据库编号。返回(新章纲, 翻译不了的代号)。已经是整数的原样保留。"""
    ids, missing = [], []
    for k in outline.get("foreshadows") or []:
        if isinstance(k, int):
            ids.append(k)
        elif k in ids_by_key:
            ids.append(ids_by_key[k])
        else:
            missing.append(str(k))
    return {**outline, "foreshadows": ids}, missing
```

`chapter.py` 超过 200 行就把这段"取剧本章纲"拆成 `huaben/pipeline/scripted.py` 里的一个函数。

### 5. 伏笔代号落库

T007 的 `normalize_plant` / `to_register`(`huaben/planting.py`):`plant` 里有 `key` 就一路带下去
(`normalize_plant` 的返回多一个 `"key": str(raw.get("key") or "").strip()`;`to_register` 登记的那条多一个 `"key"`);
`ledger_apply.py` 调 `repo.add_foreshadow` 时传 `key=f.get("key", "")`。
剧本书的伏笔**不受** `OPEN_TOTAL_LIMIT` 限制(剧本里埋多少是架构方算过的):`to_register` 加参数 `scripted: bool = False`,为真时跳过上限判断;
`chapter.py` 调用处传 `scripted=bool(ctx.book.get("scripted"))`。

### 6. 接口

`huaben/api/routes_import.py`:`POST /api/books/{book_id}/import/volume` → `import_volume(...)`;
剧本检查不过 → 400,返回体里带完整的问题列表;封卷的模型调用失败 → 502(照 `volume_arc`)。

### 7. 测试(新建 `tests/test_script_volume.py`;放不下就再分一个文件)

- `check_volume_script`:合格的 → `[]`;章数与预算之和不等、缺 `when`、引用没埋的代号、代号重复、标题重复、`plant` 缺 `truth` —— 各一条,断言问题文字里有对应关键词。
  引用**同一卷里前面的章**埋下的代号 → 合格;引用后面的章才埋的 → 不合格。
- `resolve_keys`:代号、整数、翻译不了的混在一起 → 结果与缺失列表都对。
- `import_volume`:合格 → 有进行中的卷(`beat_chapters`、`target_chapters` 对),`scripted_outlines` 里章号连续;
  非剧本书 → 报错;当前卷没写完 → 报错;检查不过 → 报错且**什么都没写进库**。
- 端到端(剧本 LLM 只提供"正文"和"入账"两种回复,**不提供章纲**——如果代码去要章纲,测试就会失败):
  导入一本书 + 一个 3 章的卷剧本(第 1 章埋 `F1`,第 3 章 `foreshadows: ["F1"]`)→ 连写 3 章 →
  三章标题与剧本一致;账本里有一条 `key="F1"` 的伏笔;第 3 章的工单里出现了这条伏笔的内容;
  再写第 4 章 → 先封卷,然后抛 step 为 "script" 的 `ChapterFailed`,且没有卷规划的模型调用。
- 非剧本书的全部现有测试原样通过。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化。
2. `tests/test_structure.py` 通过。
3. 报告里贴出端到端测试用的那份 3 章卷剧本,以及第 3 章工单(`work_order`)的完整输出。

## 这次不做

- 不做前端(书页上"等下一卷剧本"的提示沿用 `gen_error` 的现有显示)。
- 不检查"flash 写出来的正文有没有照章纲写"(以后看需要再做)。
- 不改非剧本书的任何行为。

## 审核记录

(架构方填)
