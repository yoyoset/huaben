# T014 章纲里的"原话":必须一字不改地出现在正文里

依赖:无(与 T013 互不相干,哪张先做都行)。

## 为什么

`docs/story-craft.md` 九·5:分量最重的句子(那句真心话、宣告的动作、触发反转的那一句、新形态的解放语)不能交给写作模型现场发挥——
它会把"我不跑了。"改写成"我不会再逃避了!",分量就没了。所以这些句子由架构方在章纲里写死,写作模型必须原样用;没用上的,打回重写。

## 已定的方案

### 1. 章纲多一栏 `lines`(字符串列表,可空;剧本章纲和模型章纲都认,但只有剧本会填)

### 2. 新建 `huaben/verbatim.py`(纯函数,照抄)

文件头 docstring 自己写(引用上面的"为什么")。

```python
import re

_IGNORED = re.compile(r"[\s\"'“”‘’「」『』]")  # 比对时不计空白与引号:模型常把直引号换成弯引号、在句中换行


def _squash(text: str) -> str:
    return _IGNORED.sub("", text)


def missing_lines(body: str, lines: list[str]) -> list[str]:
    """章纲要求原样出现、正文里却找不到的句子。空白与引号的差异不算。"""
    hay = _squash(body)
    return [ln for ln in lines if _squash(ln) and _squash(ln) not in hay]


def lines_feedback(missing: list[str]) -> list[str]:
    """打回重写时给作者的话。"""
    return [f"工单要求原样写出的这句话没有出现在正文里,必须一字不改地写进去:{ln}" for ln in missing]
```

### 3. 接进流水线

- `huaben/pipeline/normalize.py` 的 `normalize_outline`:返回值加 `"lines": to_text_list(d.get("lines"), "lines"),`。
  (该文件接近 200 行;超了就按 T007 卡里说的办法把 `normalize_outline` 搬到 `huaben/pipeline/normalize_outline.py`,原导入路径保持可用。)
- `huaben/pipeline/prompts.py` 的 `work_order`:在"结尾钩子"那一行**之前**,`outline.get("lines")` 非空时加:
  ```
  下面这些句子是定好的原话,必须一字不改地出现在正文里(可以配上说话人和动作,句子本身不许增删改):
  - {第一句}
  - {第二句}
  ```
- `huaben/pipeline/chapter.py` 的 `_draft_until_accepted`:在机械底线检查(`problems = ...`)里追加
  `+ lines_feedback(missing_lines(body, outline.get("lines") or []))`——缺了原话就和别的机械问题一样打回,不花入账的钱。
  运行记录照现有写法(`draft: ...`)。

### 4. 测试(新建 `tests/test_verbatim.py`)

- `missing_lines`:句子原样在正文里 → `[]`;正文把直引号换成弯引号、句中有换行 → 仍算找到;改了一个字 → 列出;`lines` 为空 → `[]`;空字符串的句子被忽略。
- `normalize_outline`:带 `lines` → 保留;不带 → `[]`。旧测试里期望字典要补 `"lines": []` 的,补上并在报告里列出。
- `work_order`:有 `lines` → 含"必须一字不改"和每一句;没有 → 不含。
- 端到端(剧本 LLM):章纲 `lines=["我不跑了。"]`,第一稿正文没有这句、第二稿有 → 第一稿被打回(运行记录里有这句话),第二稿定稿;
  第二次调用作者时的提示里含"没有出现在正文里"。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化。
2. `tests/test_structure.py` 通过。
3. 报告里贴出带两句 `lines` 的 `work_order` 完整输出。

## 这次不做

- 不做"意思差不多也算"的模糊匹配——要的就是一字不改。
- 不限制 `lines` 的条数(架构方自己掌握,一章一般不超过三句)。

## 审核记录

**通过(2026-10-03)**。架构方重跑 468 项全过;`verbatim.py` 与卡一致,接线位置正确。
**暂不部署**:生产上已导入的章纲带着 `lines`,一部署就开始强制;而第 3 章起即将由架构方重写(T016),这期间让写作模型为即将作废的稿子反复重写不值得。与 T015、T016 一起部署。
