# T029 章纲分松紧:哪些不能错,哪些放开写

依赖:无。

## 为什么

2026-10-04 重写《阴差阳错》第 9 章起,每章章纲都细到"第几场、谁说哪句",并且每章都要求结尾句一字不改。结果:

- mimo 写 8 章交了 32 稿,被编辑核对以"前后矛盾"打回 11 次(多是"哑嗓的人隔着一屋人说话,音量没交代"这类读感疑点),卡死在第 17 章;
- deepseek 第 20 章 5 稿、第 21 章 6 稿才过,全是"没写到指定的结尾句";
- Muse 同一章一稿过,自己加的对白比章纲好,但也有两处越了界(说破了伏笔、和前文事实打架)。

用户定(2026-10-04):"章纲也要分级。哪些是原则性逻辑问题,哪些是自由度高的问题……波浪起伏节奏合适";"加戏可以,大方向对就可以"。
所以:每章章纲标一个**松紧档**,关键章管得严,日常章放开;真正不能错的事单独列出来。

## 已定的方案

### 1. 章纲新增三个可选字段

| 字段 | 取值 | 含义 |
|---|---|---|
| `grip` | `"紧"` / `"中"` / `"松"` | 这一章管多严。**没填按 `"紧"` 算**(= 现在的行为,老书不受影响) |
| `must` | 字符串列表 | 不能错的事(原则性的逻辑:谁知道什么、这场谁赢、哪个谜不许说破)。可空 |
| `free` | 字符串 | 可以发挥的地方的提示。可空 |

### 2. 新模块 `huaben/grip.py`(纯函数)

`huaben/pipeline/chapter.py` 已 187 行、`prompts.py` 已 189 行,新逻辑放这里,那两个文件只加调用。

```python
GRIPS = ("紧", "中", "松")
MUST_PREFIX = "不能错:"

def grip_of(outline: dict) -> str:
    """章纲的松紧档;没填或填了别的,按"紧"。"""

def grip_lines(outline: dict) -> list[str]:
    """工单里交代松紧的几行(见下);放在工单正文之后。"""

def ending_line(outline: dict) -> str | None:
    """工单里交代结尾的那一行;章纲没有 ending 返回 None。"""

def check_ending(outline: dict) -> bool:
    """这一章的结尾原话要不要硬查:只有"紧"查。"""

def hard_contradictions(outline: dict, bad: list[str]) -> list[str]:
    """编辑核对挑出的矛盾里,哪些要打回:"紧"= 全部;"中""松"= 只有以 MUST_PREFIX 开头的。"""

def must_block(outline: dict) -> str:
    """给编辑核对用的一段;章纲没有 must 返回空字符串。"""
```

`grip_lines` 返回(第一行按档位三选一,原文照抄):

- 紧:`本章是关键章:场次、顺序、每一场的结果都照工单写,不要增删场次;对白可以润色。`
- 中:`工单是骨架:有哪几场、每一场的结果照办;骨架之间的对白、玩笑、人物的小动作可以自己加,可以接前面章节的包袱。`
- 松:`本章放开写:只要下面"不能错的"几条和结尾落点对,场次怎么排、加什么戏由你定,写得活比写得全要紧。`

`must` 非空时接着加:`【不能错的】(违反任何一条,整稿作废):`,然后每条一行 `- <内容>`。
`free` 非空时再加一行:`【可以发挥的】<内容>`。

`ending_line`:

- 紧:现在 `work_order` 里那一句,一字不改:
  `本章最后一句必须是(一字不改),写到这句就停,不要再往下写——后面的事是下一章的:<ending>`
- 中、松:`本章结尾停在下面这一刻(意思到了就行,字句可以自己写),写到这里就停,不要再往下写——后面的事是下一章的:<ending>`

`must_block`(`must` 非空时):

```
【本章不能错的】
- <第一条>
- <第二条>
正文违反上面任何一条,写进 contradictions,what 以"不能错:"开头,planned 填 false。
```

### 3. 接线

- `huaben/pipeline/normalize.py` 的 `normalize_outline`:返回的 dict 加三项——
  `"grip": to_text(d.get("grip"), "grip")`、`"must": to_text_list(d.get("must"), "must")`、`"free": to_text(d.get("free"), "free")`。
  (不在这里校验取值;取值不对由 `grip_of` 按"紧"处理。)
- `huaben/pipeline/prompts.py` 的 `work_order`:
  - 在 `lines = [标题行, outline["outline"]]` 之后紧接着 `lines += grip_lines(outline)`;
  - 末尾那段 `if outline.get("ending"): lines.append(f"本章最后一句必须是…")` 换成 `ending_line(outline)`(非 None 就追加)。
- `huaben/pipeline/prompts.py` 的 `ledger_messages`:在 `【本章章纲】…` 那一段之后、`【第 N 章正文】` 之前插入 `must_block(outline)`(为空就不插,不要留空行)。
- `huaben/pipeline/chapter.py` 的 `_draft_until_accepted`:
  - `ending_problem(body, outline.get("ending") or "")` 只在 `check_ending(outline)` 为真时算,否则当它是空列表;
  - `bad = unplanned_contradictions(ledger)` 之后:`hard = hard_contradictions(outline, bad)`;
    `hard` 非空 → 照现在的写法打回(`_reject` 的文字和 `feedback` 都用 `hard`);
    `bad` 里不在 `hard` 里的每一条,记一行不打回的留痕:`repo.log_run(conn, book_id, "check", chapter_idx=idx, note=f"矛盾(未打回):{条目}"[:300])`,然后照常往下定稿。
  - `_imported_text` 不改。
- `huaben/rhythm.py`:
  - `rhythm_problems`:某章填了 `grip` 且不在 `GRIPS` 里 → `第 N 章 grip 必须是 紧/中/松 之一(可不填)`。
  - `rhythm_warnings`:**只在这一批至少有一章填了 `grip` 时**才查下面两条(没填的章按"紧"算):
    - 连续 4 章及以上都是"紧" → `第 a~b 章连续 k 章都是「紧」,写作模型没有喘气的地方`(用现成的 `_runs`);
    - 这一批不少于 10 章,且"松"的章数不到总数的五分之一 → `这一批 N 章里只有 k 章是「松」,不到五分之一`。

改完每个 `.py` 仍须 ≤ 200 行。

## 测试

新文件 `tests/test_grip.py`:

1. `grip_of`:`{}` → 紧;`{"grip": "松"}` → 松;`{"grip": "随便"}` → 紧。
2. `grip_lines`:三档各返回对应的第一行(断言里各取一个关键词:`关键章` / `骨架` / `放开写`);
   `must=["厉九不出手"]` 时含 `【不能错的】` 和 `- 厉九不出手`;`free="斗嘴"` 时含 `【可以发挥的】斗嘴`;两者都空时只有一行。
3. `ending_line`:紧 → 含 `一字不改`;中、松 → 含 `意思到了就行`、不含 `一字不改`;没有 `ending` → `None`。
4. `check_ending`:只有紧(含没填)为真。
5. `hard_contradictions`:`bad = ["不能错:厉九出手了", "音量没交代"]`——紧 → 两条都在;中、松 → 只有第一条。
6. `must_block`:有 `must` → 含每一条和 `不能错:`;没有 → `""`。

加在现有测试文件里(找用 FakeLLM / 剧本 LLM 跑 `generate_chapter` 的现成写法照着写):

7. 章纲 `grip="中"`、带 `ending`,正文没有那句结尾 → 不因结尾打回,一稿定稿。
8. 同样的章纲不带 `grip` → 仍然因结尾打回(现有行为不变;现有测试应原样通过)。
9. `grip="松"`,编辑核对返回一条普通矛盾(`planned=false`,`what="音量没交代"`)→ 定稿,运行记录里有一条以 `矛盾(未打回)` 开头的 note。
10. `grip="松"`,编辑核对返回 `what="不能错:厉九出手了"` → 打回。
11. `work_order`:`grip="松"` 的章纲渲染出来含 `放开写`,结尾那行含 `意思到了就行`。
12. `ledger_messages`:带 `must` 的章纲,提示里含 `【本章不能错的】`;不带的不含。
13. `rhythm_problems`:`grip="硬"` 报问题;不填不报。
14. `rhythm_warnings`:5 章全填"紧" → 有"连续 5 章都是「紧」";10 章里 1 章"松"、其余"中" → 有"不到五分之一";所有章都没填 `grip` → 这两条都不出现。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数从 517 变成多少。
2. `tests/test_structure.py` 通过。
3. 不带 `grip` 的章纲,行为与改之前完全一样(现有测试不改就能过)。

## 这次不做

- 不改 `lines`(原话)的检查:列了就必须一字不改,哪一档都一样。要放松由架构方少列几句。
- 不改导入正文(`_imported_text`)那条路。
- 不改非剧本书的章纲提示词(模型自己出的章纲不带 `grip`,按"紧")。
- 不部署,不碰生产,不改 `stories/` 下任何文件。

## 审核记录

通过 2026-10-04。架构方自己重跑:`python -m pytest -q` 532 全过(原 517)。读了 diff:`grip.py` 六个函数的文字与卡一致;`chapter.py` 192 行、`prompts.py` 193 行;
不带 `grip` 的章纲走原路(现有测试只改了 `test_normalize.py` 一处期望值:章纲规整结果多了三个键)。
