# T008 伏笔清账:把已经登记的一堆旧伏笔合并、作废到 10 条以内

依赖:T007 通过。

## 为什么

T007 之后新伏笔有了纪律,但生产上已经欠着一堆旧账:《算尽仙朝》29 条、《杂役仙尊》22 条未回收。
它们每章都**全部**带进提示词,模型就被牵着去追"鞋尖蹭印""布条晃动"这些没有答案的细节;而且很多条其实指向同一件事
(回收计划里自己都写着"与……伏笔合并回收")。需要一次性清账:**指向同一个真相的合并成一条,没有意义的作废**。

这是一次显式触发的操作(照 `fill_arc` / `rebudget` 的模式),先出方案给人看(dry run),确认后才写库。

## 已定的方案

### 1. 伏笔多一个状态 `dropped`(作废)

- 不改表结构(`status` 是文本列)。`huaben/schema.py` 里那一行注释补上 `/ dropped(作废:合并进别的伏笔或判定为无意义)`。
- `huaben/repo/ledger.py` 的 `list_foreshadows(open_only=True)`:条件改成 `status NOT IN ('resolved','dropped')`。
- 在 `huaben/` 里搜 `resolved`,凡是把"不是 resolved"当成"未回收"的地方,`dropped` 都要算作**不是未回收**
  (不带进提示词、不算欠账);统计与伏笔回收报告里,`dropped` 单独计数为"作废",不算"已收"也不算"未收"。改了哪几处在报告里逐个列出。
- `repo/ledger.py` 新增 `set_foreshadow_plan(conn, fid, payoff_plan, commit=True)`:只更新 `payoff_plan`。

### 2. 新建 `huaben/pipeline/tidy_foreshadows.py`

纯函数(照抄):

```python
KEEP_MAX = 10


def normalize_tidy(d, open_ids: set[int]) -> dict | None:
    """模型的清账方案 → 合法形状。keep:[{id, truth}];drop:[id]。
    规则:只认账本里确实未回收的编号;同一编号既在 keep 又在 drop 时算 keep;没提到的编号一律保留(宁可少清,不误删);
    keep 里 truth 为空的也保留、只是不改它的回收计划;keep 超过 KEEP_MAX 条或一条都没有 → None(方案不合格)。"""
    if not isinstance(d, dict) or not isinstance(d.get("keep"), list):
        return None
    keep = {}
    for k in d["keep"]:
        if isinstance(k, dict) and isinstance(k.get("id"), int) and k["id"] in open_ids:
            keep[k["id"]] = str(k.get("truth") or "").strip()
    drop = [i for i in d.get("drop") or [] if isinstance(i, int) and i in open_ids and i not in keep]
    unmentioned = open_ids - set(keep) - set(drop)
    if not keep or len(keep) + len(unmentioned) > KEEP_MAX:
        return None
    return {"keep": [{"id": i, "truth": t} for i, t in sorted(keep.items())], "drop": sorted(set(drop))}
```

`tidy(conn, llm, settings, book_id, apply: bool) -> dict`:
取未回收伏笔(≤ `KEEP_MAX` 条时直接返回 `{"keep": [], "drop": [], "skipped": "未回收伏笔不超过 10 条,不需要清账"}`)→
调模型(步骤名 `"foreshadow_tidy"`,复用 `volume.py` 的 `_ask`;`normalize_tidy` 返回 None 就抛 `ParseError("清账方案不合格")`)→
`apply` 为真时在**一个事务**里:`drop` 的全部 `update_foreshadow(status="dropped")`;`keep` 里 `truth` 非空的 `set_foreshadow_plan`;
并写一条运行记录 `清账:保留 N 条,作废 M 条: [编号…]`。
返回方案,并给每个编号带上原文方便人看:`{"keep": [{"id","content","truth"}], "drop": [{"id","content"}], "applied": bool}`。

### 3. 提示词(新增函数 `tidy_messages(ctx)`,放在 `tidy_foreshadows.py` 里;原文照抄)

system:`你是长篇连载小说的责任编辑。严格只输出 JSON,不要任何解释或代码围栏。`

user:

```
{render_bible(ctx.bible)}

【全书梗概】
{梗概,没有就写"(尚无)"}

【本卷目标】{goal}
【本卷节拍】{节拍用"→"连起来}

【已登记、尚未回收的伏笔】
{每条一行:#编号 第N章埋:内容(计划:回收计划)}

这些伏笔登记得太多太碎:很多条指向同一个秘密,很多只是来历不明的痕迹、记号、纸条,当初埋的时候并没有想好答案。
请清账,最后保留不超过 10 条:
1. 指向同一个秘密的,只保留最能代表它的一条,其余放进 drop;
2. 说不出背后真相、或者真相对后面剧情没有影响的,放进 drop;
3. 保留的每一条,在 truth 里写出它背后的真相是什么、将来怎么改变剧情——现在就定下来,不要写"后续揭示"。
   真相要与世界观、人物卡、已发生的剧情自洽;几条保留的伏笔之间最好能互相印证,指向本卷目标或全书的核心谜团。
只输出如下结构的 JSON:
{"keep": [{"id": 伏笔编号(整数), "truth": "背后的真相"}], "drop": [伏笔编号(整数)]}
```

### 4. 接口

`huaben/api/routes_craft.py`(超 200 行就新建 `routes_ledger.py` 并照其它路由文件的方式注册):
`POST /api/books/{book_id}/foreshadows/tidy?apply=0|1`(默认 0 = 只出方案不写库)。异常处理与 `volume_arc` 一致。**不做前端。**

### 5. 测试(新建 `tests/test_tidy_foreshadows.py`)

- `normalize_tidy`:
  - 正常:13 条未回收,keep 4 条、drop 9 条 → 通过,drop 排好序;
  - keep 里有不存在的编号 → 被忽略;
  - 同一编号在 keep 和 drop → 算 keep;
  - 没提到的编号算保留:13 条里 keep 3、drop 2(剩 8 条没提)→ 3+8=11 > 10 → `None`;
  - keep 为空 → `None`;`d` 不是字典 → `None`。
- `tidy`(剧本 LLM):`apply=False` → 账本不变、返回里 `applied` 为 False 且每条带 `content`;
  `apply=True` → drop 的状态变 `dropped`、keep 的 `payoff_plan` 变成 truth、`list_foreshadows(open_only=True)` 只剩保留的;
  未回收 ≤10 条 → 不调模型,返回 `skipped`。
- `dropped` 的伏笔不出现在 `load_context(...).foreshadows` 里。
- 接口:`apply` 缺省时不写库;模型两次给出不合格方案 → 502。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化。
2. `tests/test_structure.py` 通过。
3. 报告里列出"搜 `resolved` 后改了哪几处、各自怎么处理 `dropped`"。
4. 报告里贴出 `tidy_messages` 对一本有 3 条伏笔的假书渲染出的完整 user 文本。

## 这次不做

- 不自动触发,不对生产执行(架构方验收后先在生产上 dry run,把方案给用户看,用户同意才 apply)。
- 不做前端按钮。
- 不删除任何伏笔记录(`dropped` 只是状态,随时能改回来)。

## 审核记录

(架构方填)
