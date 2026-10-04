# T030 打回的理由分轻重:末稿放行、碎句分两段、写作要求分"必须"和"尽量"

依赖:T029(已通过)。

## 为什么

用户 2026-10-04:"全部的限制规范……都应该分轻重缓急,采用分级复合方式,不能一刀切。"
架构方把现有的限制过了一遍,T029 之后还剩三处一刀切:

1. **所有打回理由一样重,而且永不让步。** 一章三稿都不过就整章失败、退避、再来三稿,没有尽头。
   2026-10-04 实测:mimo 在第 17 章卡了一个多小时;deepseek 第 22 章三稿全因"结尾句差几个字"被退。
   "读者没有下一章可读"比"结尾句差几个字"糟得多,但现在两者的处理是反的。
2. **碎句是一条线**:每百字逗号 9.0 个就整稿打回,8.9 个没事。实测正常的章 6~8,真切碎的章 10 以上;Muse 写的第 24 章正好 8.0。
3. **写作提示里九条"硬性要求"并排**:"只输出正文"和"招牌能力要有名有姓"是同一级,模型分不出哪条是底线。

## 已定的方案

### 1. 打回理由分两类(`huaben/grip.py` 加函数,`chapter.py` 改 `_draft_until_accepted`)

| 类 | 包括 | 处理 |
|---|---|---|
| 致命 | `draft_problems`(篇幅不足、拒绝、标点缺失、繁体、大段重复)、`copy_problems`、`restage_problems`;稿子被截断;违反 `must` 的矛盾 | 哪一档、哪一稿都打回(现状不变) |
| 重 | 缺原话(`lines_feedback`)、结尾原话(只有"紧"档才查)、碎句超过硬线、"紧"档的普通矛盾 | "紧"档:一直打回。"中""松"档:**最后一稿**不再因这一类打回,留痕后放行 |

在 `huaben/grip.py` 加:

```python
def lenient(outline: dict, attempt: int, max_attempts: int) -> bool:
    """这一稿是不是"末稿放行":档位不是"紧",而且是最后一稿,而且总稿数大于 1。"""
```

`_draft_until_accepted` 里机械检查那一段改成(变量名可以不同,逻辑照这个):

```python
fatal = draft_problems(...) + copy_problems(...) + restage_problems(...)
heavy = lines_feedback(missing_lines(...)) + ending + chop_problems(body)   # ending 仍按 T029:只有"紧"档才算
if fatal or (heavy and not lenient(outline, attempt, settings.max_write_attempts)):
    _reject(conn, book_id, idx, "draft: " + "; ".join(fatal + heavy)); feedback = fatal + heavy; continue
for p in heavy:   # 走到这里且 heavy 非空 = 末稿放行
    repo.log_run(conn, book_id, "check", chapter_idx=idx, note=f"末稿放行(未打回):{p}"[:300])
```

矛盾那一段不改(T029 已经分好:`hard_contradictions` 非空就打回,违反 `must` 的在任何一稿都打回)。
截断(`draft.truncated`)那一段不改。

### 2. 碎句分两段(`huaben/pipeline/chop.py`)

- 新常量 `CHOP_HARD = 10.0`;`CHOP_LIMIT = 9.0` 保留,含义改为"提醒线"。
- `chop_problems(text)`:密度 **大于 `CHOP_HARD`** 才返回打回理由(文字不变)。
- 新函数 `chop_note(text) -> str`:密度大于 `CHOP_LIMIT` 且不大于 `CHOP_HARD` → 返回 `f"句子偏碎(每百字 {d:.1f} 个逗号,正常是 6~8 个)"`;否则 `""`。不足 `CHOP_MIN_CHARS` 也返回 `""`。
- `_draft_until_accepted` 在定稿前(和 `repetition_note` 那几行放一起):`chop_note(body)` 非空就 `repo.log_run(conn, book_id, "check", chapter_idx=idx, note=...)`,不打回。
- 文件头注释补一句:为什么分两段(上面"为什么"第 2 条的数字)。

别处用到 `CHOP_LIMIT` 或 `chop_problems` 的(`grep -rn "chop" huaben tests` 查一遍,例如接句工具 `smooth*.py`):保持它们现在的判断阈值不变——
如果它们是靠 `chop_problems` 判断的,改成自己比 `comma_density(text) > CHOP_LIMIT`,不要因为这张卡把它们的线抬到 10.0。

### 3. 写作提示的要求分两级(`huaben/pipeline/prompts.py` 的 `write_messages`)

`hard` 那一段改成下面的结构(各条的文字用现有的常量和现有的句子,只改分组、标题和序号):

```
现在写第 N 章正文,约 W 字。
【必须】
1. 只输出正文,不要标题、不要解释、不要状态栏、不要任何前后缀;
<consistency_rule(outline) 的内容——它自带"2. "开头,原样用>
3. 全文使用完整的中文标点;
4. 结尾落在工单指定的钩子上。
【尽量做到(写法上的习惯;和工单冲突时听工单的)】
- 按【写法设定】写,保持风格指纹与样章的语感;
- 推理、算账写给读者看得懂:……(现有第 4 条全文)
- <SIGNATURE_RULE>
- <SPEECH_RULE>
- <REPETITION_RULE>
- <REALISM_RULE>
```

`opening_rule` 非空时,`【开篇要求】…` 那一行放在最后(现状就是放在第 8 条之后,保持在末尾即可)。
`prompts.py` 现在 193 行,改完须 ≤ 200 行;超了把这段文字的拼装挪到 `rules.py` 里的一个函数。

## 测试

`tests/test_grip.py` 加:

1. `lenient`:`{"grip":"中"}`、attempt=3、max=3 → True;attempt=2 → False;`{"grip":"紧"}` 或没填、attempt=3 → False;`{"grip":"松"}`、attempt=1、max=1 → False。

`tests/test_chop.py`(没有就新建;已有碎句测试的文件里加也行):

2. 密度 9.5 的文本(自己拼:够 500 字)→ `chop_problems` 返回空,`chop_note` 非空且含 `偏碎`。
3. 密度 10.5 → `chop_problems` 非空,`chop_note` 为空。
4. 密度 7 → 两个都空。

流水线测试(照现有用 FakeLLM / 剧本 LLM 跑 `generate_chapter` 的写法):

5. `grip="中"`、`lines=["我不跑了。"]`,三稿正文都没有这句 → 第三稿定稿;运行记录里有 `末稿放行(未打回)` 开头的 note,前两稿各有一条 `draft:` 打回。
6. 同样的章纲但 `grip="紧"`(或不填)→ 三稿后 `ChapterFailed`(现有行为)。
7. `grip="松"`,三稿都篇幅不足(致命)→ 仍然 `ChapterFailed`。
8. `grip="松"`,编辑核对三稿都返回 `不能错:` 开头的矛盾 → 仍然 `ChapterFailed`。
9. 密度 9.5 的正文、其余都合格 → 一稿定稿,运行记录里有 `句子偏碎` 的 note。

`tests/test_prompts.py`:

10. `write_messages` 的输出里:`【必须】` 在 `【尽量做到` 之前;`只输出正文` 在两者之间;`SIGNATURE_RULE`、`SPEECH_RULE` 的文字在 `【尽量做到` 之后;不再出现 `硬性要求` 四个字。
    现有断言里依赖旧序号(如 `"5. "`)的,改成断言内容还在。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数从 532 变成多少。
2. `tests/test_structure.py` 通过(单文件 ≤ 200 行)。
3. 不带 `grip` 的章纲:除了碎句硬线从 9.0 变成 10.0、写作提示的分组变了之外,行为与改之前一样。

## 这次不做

- 不改"致命"类各检查的阈值(篇幅 40%、照抄 8%、重演 0.12/0.06)。
- 不改入账核对的提示词,不改 `must` 的规则(T029)。
- 不改节奏检查(`rhythm.py`):它本来就分"问题(拦导入)"和"提醒(不拦)"两级。
- 不改导入正文那条路。不部署,不碰生产,不改 `stories/`。
