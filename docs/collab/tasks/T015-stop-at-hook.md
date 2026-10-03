# T015 写到钩子就停:结尾原话必须落在最后几行

依赖:T014 通过(共用 `huaben/verbatim.py`)。

## 为什么

第一本剧本书《弄假成真》上线后,架构方读了生产上写出来的第 1 章:章纲的结尾钩子是女修揪住陈皮后领说“戏不错。跟我走一趟。”——
写作模型写到这里没有停,又往下写了六百多字,把第 2 章的事(塞腰牌、离开镇子、天快亮了)提前写完了。结果第 2 章的章纲和已经写出来的第 1 章对不上。
硬性要求第 9 条“结尾落在工单指定的钩子上”只是一句话,没有任何检查。写作模型有“把话说完”的倾向,章纲越往后的内容它越想顺手带上。

## 已定的方案

章纲多一栏 `ending`(一句原话,可空):这句话必须出现在正文的**最后 200 个字**里。没有,就打回,并明确告诉作者“写到这句就停”。

### 1. `huaben/verbatim.py` 增加(照抄)

```python
ENDING_WINDOW = 200  # 结尾原话必须落在正文最后这么多字里


def ending_problem(body: str, ending: str) -> list[str]:
    """章纲指定了结尾原话,正文却没有停在那里(没出现,或出现之后又往下写了一大段)。"""
    want = _squash(ending or "")
    if not want:
        return []
    hay = _squash(body)
    if want not in hay:
        return [f"正文没有写到工单指定的结尾。最后一句必须是(一字不改):{ending}"]
    if want not in hay[-ENDING_WINDOW:]:
        return [f"正文写过头了:工单指定的结尾“{ending}”出现之后又往下写了一大段。写到这句就停,后面的事留给下一章,把多出来的全部删掉。"]
    return []
```

### 2. 接进流水线

- `normalize_outline`:返回值加 `"ending": to_text(d.get("ending"), "ending"),`。
- `work_order`:最后一行现在是 `结尾钩子:{hook}`。在它**后面**,`outline.get("ending")` 非空时再加一行:
  `本章最后一句必须是(一字不改),写到这句就停,不要再往下写——后面的事是下一章的:{ending}`
- `chapter.py` 的机械底线检查里追加 `+ ending_problem(body, outline.get("ending") or "")`。
- `huaben/script_import.py` 的 `check_volume_script`:不要求 `ending` 必填(不改)。

### 3. 测试(加在 `tests/test_verbatim.py`)

- `ending_problem`:结尾原话在最后 200 字里 → `[]`;正文里根本没有 → 一条,含“没有写到”;原话出现在中间、后面还有 300 字 → 一条,含“写过头了”;`ending` 为空 → `[]`;引号与换行的差异不算。
- `work_order`:有 `ending` → 含“写到这句就停”;没有 → 不含。
- 端到端(剧本 LLM):章纲 `ending="跟我走一趟。"`,第一稿在这句之后又写了 400 字、第二稿停在这句 → 第一稿被打回(运行记录含“写过头了”),第二稿定稿。
- 旧测试的期望字典补 `"ending": ""`,在报告里列出。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化。
2. 报告里贴出三种情况下 `ending_problem` 的真实输出。

## 这次不做

- 不改已经写好的章。
- 不对没有 `ending` 的章纲做任何结尾检查。

## 审核记录

通过 2026-10-03。架构方自己重跑 `python -m pytest -q`:481 全过(478→481);读了 `verbatim.py`、`prompts.py`、`chapter.py`、`normalize.py` 的 diff,
与卡里"照抄"的部分一致;`test_verbatim.py` 的三项新测试覆盖了 5 种 `ending_problem` 情形、工单停笔行有/无、端到端"写过头被打回→第二稿定稿"。
旧测试期望字典补 `"ending": ""`(`test_normalize.py`)已在报告里列出。
