# T016 剧本制(四):导入架构方写好的正文

依赖:无(与 T013~T015 互不相干)。

## 为什么

2026-10-03 用户读了《弄假成真》前几章后决定:正文也可以由架构方(Claude)来写——写作模型的文笔够用,毛病在"不完全照章纲走"
(写过钩子、提前泄露后面的设定、改写关键句)。所以要能把**写好的正文**导进来:有导入正文的章,用导入的;没有的章,照旧由写作模型按章纲写。
两种可以混着用(比如要紧的章由架构方写,过渡章给写作模型)。

记账(章摘要、人物现状、伏笔登记、世界事实)照旧由写作模型做——后面的章要靠这些接上。

## 已定的方案

### 1. 数据库(迁移 21)

```sql
CREATE TABLE scripted_bodies (
  book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL,
  body TEXT NOT NULL,
  PRIMARY KEY(book_id, idx)
);
```

`huaben/repo/scripts.py` 加:`save_scripted_bodies(conn, book_id, {idx: body}, commit=True)`(同一章再导一次就覆盖)、
`get_scripted_body(conn, book_id, idx) -> str | None`。

### 2. 导入(`huaben/script_import.py`;超 200 行就拆出 `huaben/script_text.py`)

```python
def import_chapter_texts(conn, book_id: int, chapters: list[dict]) -> dict:
    """[{"idx": 章号, "body": 正文}] → 存进 scripted_bodies。返回 {"saved": [章号…]}。"""
```

每一条的硬检查,任何一条不过就整批不存,把所有问题一起报出来(`ScriptImportError`):

- 这本书必须是剧本书;
- `idx` 是整数,这一章必须**已有剧本章纲**(正文要对着章纲记账);
- 这一章**还没有定稿**(已定稿的章不能靠导入改写——那要走"重新导入整本书");
- `body` 清洗(`clean_draft`)后不少于 500 字;
- 同一批里章号不重复。

### 3. 写章时用导入的正文(`huaben/pipeline/chapter.py`)

`_draft_until_accepted` 开头:`given = repo.get_scripted_body(conn, book_id, idx)`。有的话走下面这条分支,**不调用作者模型**:

1. `body = clean_draft(given)`,存进章节,写一条运行记录 `write: 来自导入的正文`。
2. 机械检查(`draft_problems` 等)**照跑,但只留痕不打回**:每条问题写一条运行记录 `导入正文的提醒(未打回):…`。
   (这是架构方写的稿,没有"重写"这一步;字数偏差之类由架构方自己看。)
3. 入账:照旧 `_record(...)`。两次都解析失败 → `_fail(..., "ledger", "导入正文的入账两次都无法解析")`。
4. 入账报出的未计划矛盾(`unplanned_contradictions`)**不打回**,逐条写运行记录 `导入正文与账本的出入(未打回):…`,然后照常 `apply_ledger`。
5. 后面的伏笔登记、重复提醒、`accepted` 记录与原流程相同。记 `accepted at attempt 1(导入)`。

没有导入正文的章,原流程一行不改。`chapter.py` 超 200 行就把这条分支拆到 `huaben/pipeline/scripted.py`。

### 4. 接口(`huaben/api/routes_import.py`)

`POST /api/books/{book_id}/import/texts`,请求体 `{"chapters": [{"idx": 1, "body": "…"}]}` → `{"saved": [1, …]}`;检查不过 → 400,带完整的问题列表。

### 5. 测试(新建 `tests/test_script_text.py`)

- `import_chapter_texts`:合格 → 存下,再导同一章 → 覆盖;非剧本书、没有章纲的章、已定稿的章、不足 500 字、章号重复 —— 各报错,且**一条都没存**。
- 端到端(剧本 LLM **只提供入账的回复,不提供正文**——代码要是去要正文,测试就失败):导入一本书 + 3 章章纲 + 第 1、2 章正文 →
  写第 1 章:正文与导入的一致(清洗后)、运行记录有"来自导入的正文"、没有作者模型的调用;第 3 章没有导入正文 → 走原流程(这时给剧本 LLM 补上正文回复)。
- 导入正文过短于目标字数 → 只有"提醒(未打回)"的运行记录,章照常定稿。
- 入账报一条未计划的矛盾 → 章照常定稿,运行记录里有"出入(未打回)"。
- 入账两次坏 JSON → `ChapterFailed`,step 为 ledger。
- 非剧本书的全部现有测试原样通过。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化。
2. `tests/test_structure.py` 通过。
3. 报告里贴出端到端测试里第 1 章的运行记录(pipeline_runs 的 step 与 note)。

## 这次不做

- 不做"改写已定稿的章"、不做回滚到第 N 章(要重来就删书重导,由架构方操作)。
- 不做前端。

## 审核记录

通过 2026-10-03。架构方自己重跑:`python -m pytest -q` 481 全过;`len(MIGRATIONS)` 实测 21;`test_structure.py` 过(`chapter.py` 182 行、`script_text.py` 45 行)。
读了全部 diff:整批原子(先收集全部问题、通过才存)、有导入稿的章不调作者模型(端到端测试断言调用记录里没有"现在写第 1/2 章正文")、
机械检查与账本矛盾只留痕、入账两次坏 JSON 走 `_fail(...,"ledger")`,都与方案一致;无导入稿的章原流程未动。

执行方在报告里如实写了迁移 21 编辑没落盘的事故和排查中"以为 HEAD 被回退→实测推翻"的修正,这样写是对的。关于它提的问题:
这个仓库同一时间只有一个人动共享文件(架构方只改 `docs/` 与 `stories/`,不碰 `huaben/`),所以不会撞;以后改 `migrations.py` 仍按它说的做,写完读回条数。

留给以后(不是这次的缺陷):导入稿目前不跑"章纲原话 / 结尾原话"检查。架构方自己写稿时自己核对即可;若发现总是漏,再出一张卡把这两项也作为"提醒(未打回)"留痕。
