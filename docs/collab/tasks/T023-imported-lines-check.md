# T023 导入的正文也查"原话"和"结尾",只留痕

依赖:无。

## 为什么

T016 验收时留下的:导入的正文(架构方写好的稿)目前不跑"章纲原话 / 结尾原话"检查,漏了也没有任何记录。
这张卡让这两项也查,但**只留痕、不打回**(导入稿没有"重写"这一步)。

## 已定的方案

只改 `huaben/pipeline/chapter.py` 的 `_imported_text`:那个"只留痕不打回"的 `for p in (...)` 加法式子的末尾,再加两项:

```python
+ lines_feedback(missing_lines(body, outline.get("lines") or []))
+ ending_problem(body, outline.get("ending") or "")
```

这两个函数 `chapter.py` 已经导入了(`_draft_until_accepted` 在用)。运行记录的写法不变:`导入正文的提醒(未打回):{p}`。
`chapter.py` 现在 185 行,改完不许超过 200 行。

## 测试(新建 `tests/test_imported_lines.py`)

照 `tests/test_chop.py` 里 `test_imported_chopped_text_only_warns` 的搭法(导入书 → 导入 1 章章纲 → 导入正文 → `generate_chapter`):

- 章纲带 `"lines": ["我不跑了。"]`,正文里没有这句 → 章照常定稿(`status == "accepted"`),
  运行记录里有一条同时包含 `导入正文的提醒(未打回)` 和 `我不跑了。` 的 note。
- 章纲带 `"ending": "他站起来了。"`,正文不以它结尾 → 章照常定稿,运行记录里有一条同时包含 `导入正文的提醒(未打回)` 和 `他站起来了。` 的 note。
- 正文里原话和结尾都在 → 运行记录里没有包含 `原样写出` 或 `指定的结尾` 的提醒。

`test_script_volume.py` 里的 `ch(n)` 造章纲时若不支持传 `lines` / `ending`,就在测试里拿到它返回的字典后自己加这两个键。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化(现在 497)。
2. `tests/test_structure.py` 通过;报告写 `chapter.py` 的行数。

## 这次不做

- 不打回导入稿;不改提示词;不改 `verbatim.py`。

## 审核记录

通过 2026-10-04(执行:mimo-v2.6-flash,450 秒)。架构方重跑 507 全过;`chapter.py` 187 行;diff 只有卡里那两项。已部署。
