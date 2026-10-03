# T010 剧本制(一):导入一本由架构方写好的书

依赖:T007 通过(要用它的 `plant` 章纲栏)。

## 为什么

见 `docs/architecture.md` 第 5.5 节"剧本制"。全书设计(世界、人物、真相层、文风)由架构方写成 `stories/<书名>/book.json`,
不再经过"开书对话 → 模型定稿"。本卡做"把这份文件变成一本可以连载的书"。

## 已定的方案

### 1. 数据库(迁移 19,一条迁移里两句)

```sql
ALTER TABLE books ADD COLUMN scripted INTEGER NOT NULL DEFAULT 0;
ALTER TABLE bibles ADD COLUMN secrets TEXT NOT NULL DEFAULT '';
```

- `scripted=1`:剧本书,章纲与卷规划只来自导入。
- `secrets`:真相层(只有作者知道的答案)。**只存不用**:不许出现在任何发给模型的提示词里,也不许出现在任何给读者的接口返回里
  (它只是给架构方留档)。加一个测试钉住这一点。

### 2. 把"把一份圣经写进数据库"从开书流程里拆出来

`huaben/opening/service.py` 的 `_extract_bible` 后半段(`with tx(conn):` 里那一整段:更新书信息、存圣经、清人物、逐个登记人物)
拆成一个独立函数,放进新文件 `huaben/opening/save_bible.py`:

```python
def save_parsed_bible(conn, book_id: int, bible: dict, style_samples: list[str], extracted_msgs: int = 0,
                      secrets: str = "") -> None:
```

行为与现在完全一致(同一事务、同样的字段),只是多存一个 `secrets`。`_extract_bible` 改为调用它。**开书流程的行为不许变**,现有测试必须原样通过。

### 3. 导入

新建 `huaben/script_import.py`:

```python
def import_book(conn, data: dict) -> int:
    """book.json → 一本 status='serializing'、scripted=1 的书,返回 book_id。此时还没有卷:要再导入卷剧本(T011)才会开始写。"""
```

`data` 的结构(也是 `stories/<书名>/book.json` 的格式):

```json
{
  "profile": "读者名字(必须已存在,找不到就报错并列出现有读者)",
  "craft": {"narrative": "...", "prose": "...", "imagination": "...", "foreshadow": "...", "pacing": "...", "notes": "..."},
  "bible": { 与 huaben/opening/prompts.py 的 FINALIZE_SCHEMA 完全相同的结构 },
  "style_samples": ["样章片段,可空数组"],
  "secrets": "真相层全文"
}
```

- `bible` 用现成的 `parse_bible` 做校验(它吃 JSON 文本,就 `json.dumps` 一下再喂;不合格抛出的错原样向上传)。
- `craft` 用 `normalize_craft` 规整后存进 `books.craft`。
- 建书、存圣经、置 `status='serializing'`、`scripted=1` 要在调用方看来是原子的:中途出错不能留下半本书(出错就删掉刚建的书)。
- 同一个读者名下已有同名的书 → 报错"已有同名的书",不覆盖。

### 4. 接口

`POST /api/import/book`(请求体就是上面的 JSON)→ `{"book_id": N}`;校验失败 → 400 并带原因。
放进新文件 `huaben/api/routes_import.py`,注册方式照其它路由文件。**不做前端。**

### 5. 剧本书没有卷的时候不许让模型去规划

`huaben/pipeline/volume.py` 的 `ensure_active_volume`:在"没有进行中的卷就规划一卷"之前,如果这本书 `scripted` 为真,
改为抛 `ChapterFailed("这一卷已经写完,等下一卷剧本导入后继续", step="script")`;
当前卷写满时**照旧先封卷**,封完再抛。
`huaben/human_errors.py`:让这种错误(`step == "script"`)在书页上显示的人话就是那句"这一卷已经写完,等下一卷剧本导入后继续"
(看 `explain` 现在怎么处理别的 step,照样加一种)。

### 6. 测试(新建 `tests/test_script_import.py`)

- 导入一份最小的合法 `book.json` → 书存在、`scripted=1`、`status='serializing'`、圣经各字段与账本人物(含 core、signature)都在,`secrets` 存下。
- 读者不存在 → 报错且没有留下书;`bible` 缺 `world` → 报错且没有留下书;同名 → 报错。
- `secrets` 不出现在:`outline_messages` / `write_messages` / `ledger_messages` / `plan_messages` 的任何一条消息里,也不出现在
  `GET /api/books/{id}` 等读者接口的返回里(在 `secrets` 里放一个独特的标记字符串,全文搜它)。
- 剧本书没有卷时 `ensure_active_volume` 抛 `ChapterFailed`(step 为 "script"),且**没有任何模型调用**(用会计数的替身 LLM);
  非剧本书行为不变。
- 接口:合法 → 200 与 `book_id`;不合法 → 400。
- 开书流程的现有测试全部原样通过(不许改它们的断言)。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化。
2. `tests/test_structure.py` 通过。
3. 报告里说明 `save_parsed_bible` 拆出后 `opening/service.py` 少了多少行、哪些测试覆盖了"行为不变"。

## 这次不做

- 不导入卷和章纲(T011)。
- 不做前端页面;不删旧的开书流程。
- 不删任何已有的书(清空旧书由架构方在全部就绪后做,先备份)。

## 审核记录

(架构方填)
