# T005 上一轮审查留下的三处小修

## 为什么

架构方审查路线 32、56~70 的提交时发现三处纯机械的遗留问题。都不改行为方向,只是收拾干净。

## 改哪些文件

### 1. `huaben/pipeline/prompts.py`:删掉死代码

`_consistency_rule(outline)` 这个函数(带下划线的那个)已经没人调用——同样的函数搬到了 `rules.py` 叫 `consistency_rule`,
旧的忘了删。**删除 `_consistency_rule` 整个函数**。先在 `huaben/` 和 `tests/` 里搜 `_consistency_rule` 确认没有别的调用;
有的话改成调用 `consistency_rule`,并在报告里列出。

### 2. `huaben/pipeline/prompts.py` 的 `write_messages`:硬性要求的编号乱了

现在是 `1.` `2.` `3.` `4.`,然后四条没有编号的规则,然后 `6.`(没有 5)。关思考的模型对编号列表更听话,编号断了等于把后面几条降了级。
改成连续编号,文字不变,只加编号:

```
1. 只输出正文……(不变)
2. (consistency_rule 的输出,不变)
3. 按【写法设定】写……(不变)
4. 推理、算账写给读者看得懂……(不变)
5. {SIGNATURE_RULE}
6. {SPEECH_RULE}
7. {REPETITION_RULE}
8. {BOND_RULE}
9. 结尾落在工单指定的钩子上。
```

`opening_rule(ctx.next_idx)` 只在前三章有内容:有内容时作为单独一行放在第 9 条**之前**、不编号(前面加"【开篇要求】");
为空时**不要留空行**。

### 3. `huaben/pipeline/rules.py` 的 `title_rule`:措辞错了

`"书名已有章节标题(新章标题不得与这些重复…"` 里的"书名"是笔误,改成 `"本书已有章节标题(新章标题不得与这些重复…"`。其余不变。

## 测试

- 加一个测试:`write_messages` 的输出里,硬性要求一段依次出现 `1.` 到 `9.`,没有跳号;第 4 章以后的书不出现"【开篇要求】",
  也不出现连续两个空行。
- 加一个测试:`title_rule(["甲"])` 以"本书已有章节标题"开头。
- 旧测试里如果断言了"书名已有章节标题"或 `6. 结尾落在`,改成新文字(报告里列出改了哪几处)。

## 验收标准

1. `python -m pytest -q` 全过。
2. `grep -rn "_consistency_rule" huaben tests` 没有任何输出。
3. `tests/test_structure.py` 通过。

## 这次不做

- 不调整这些规则的内容、顺序和取舍(哪些规则该留、该合并,是架构方的事)。

## 审核记录

(架构方填)
