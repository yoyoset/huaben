# T006 常识:人要睡觉,事情大多在白天办(场景时间)

## 为什么

2026-10-03 用户:"他不分白天黑夜吗?晚上不睡觉吗?为什么四点钟要出门去别的地方?关键是别的地方也不睡觉吗?"

架构方查生产:《算尽仙朝》13 章里有 6 章发生在三更/四更/子时/半夜/夜里(第 1、2、5、7、9、10 章),
主角半夜去万宝楼做交易、半夜翻账、半夜递陈情,对面的人也都醒着当值。

原因:系统里**没有任何地方记录"现在是什么时候"**。章纲只写"发生什么",不写"什么时候";作者每章自己挑一个时间,
而"夜里"最容易写出气氛,于是章章半夜,前后两章的时间也接不上。提示词里也没有任何一句关于作息的常识要求。

## 已定的方案

1. 章纲多一栏 `when`:本章发生在什么时候(相对上一章过了多久 + 时段)。章纲本来就整份存进数据库(`chapters.outline` 是 JSON),
   所以**不需要改数据库**。
2. 写下一章章纲时,把最近几章的 `when` 列给编辑看,他才接得上、也看得见"已经连着几章在半夜了"。
3. 一条作息常识规则,给编辑和作者。作者那边的硬性要求**不增加条数**:用它替换掉第 8 条(伙伴关系)——
   那一条说的是"本卷至少让一段关系有实质推进",是卷和章纲层面的要求,章纲和卷规划里已经有了,作者每章都看一遍没有用。

## 改哪些文件

### 1. 新建 `huaben/clock.py`(纯函数与常量,照抄)

文件头 docstring 自己写:把"为什么"里的实测(13 章里 6 章在半夜)和原因写进去。

```python
import json

WHEN_SCHEMA = ('  "when": "本章发生在什么时候:相对上一章过了多久(紧接着 / 当天晚些 / 第二天 / 几天后),'
               '加上时段(清晨、上午、午后、傍晚、夜里);一章跨了几天也写明",')

REALISM_RULE = ("人物活在正常的作息里:夜里要睡觉;衙门、店铺、执事堂、库房、藏经阁这类地方夜里不办事、没人当值,"
                "除非设定里写明。事情大多放在白天做;只有必须避人的事才放在夜里,并且要让读者看得出为什么非夜里不可、"
                "对方为什么这个时候也醒着。不要一连几章都在半夜。熬了夜,第二天要有代价(困、误事、被人看出来)。"
                "时间要接得上:上一章停在夜里,本章要么接着写当夜,要么明说过了多久。")


def recent_when(recent: list[dict]) -> str:
    """最近几章各发生在什么时候(取自各章章纲的 when)。旧章没有这一栏就跳过;一条都没有返回空串。"""
    lines = []
    for c in recent:
        try:
            when = json.loads(c.get("outline") or "{}").get("when", "")
        except ValueError:
            when = ""
        if when:
            lines.append(f"- 第{c['idx']}章:{when}")
    return ("最近几章的时间:\n" + "\n".join(lines) + "\n本章的时间要和它们接得上。\n") if lines else ""
```

### 2. `huaben/pipeline/normalize.py` 的 `normalize_outline`

返回的字典里加一项:`"when": to_text(d.get("when"), "when"),`(可空,不因缺它打回章纲)。只加这一行。

### 3. `huaben/pipeline/prompts.py`

- `OUTLINE_SCHEMA`:在 `"outline"` 那一行**后面**插入 `WHEN_SCHEMA` 的内容(用字符串拼接或直接把那一行文字写进去,二选一,结果文字必须与 `WHEN_SCHEMA` 一致)。
- `outline_messages`:在 `{recent_hooks(ctx)}` **前面**加 `{recent_when(ctx.recent)}`;在 `{pacing_rule(ctx)}\n` 后面加 `{REALISM_RULE}\n`。
- `work_order`:在标题行、`outline["outline"]` 之后加一行(`when` 非空时才加):`f"本章时间:{outline['when']}"`。
  用 `outline.get("when")` 取,旧章纲没有这一栏不能报错。
- `write_messages` 的硬性要求:第 8 条从 `BOND_RULE` 换成 `REALISM_RULE`(编号不变,仍是 1~9)。
  `BOND_RULE` 在 `outline_messages` 和卷规划里**保留不动**。换完后如果 `prompts.py` 里不再用到 `BOND_RULE` 以外的导入变化,照实调整 import。
- `prompts.py` 现在 171 行。改完超过 200 行的话,把 `recent_hooks` 整个函数搬到 `huaben/pipeline/rules.py`(并在 `prompts.py` 里导入),不要压缩代码。

### 4. 测试(新建 `tests/test_clock.py`)

- `recent_when`:两章有 `when`、一章没有 → 输出只含那两章,且含"接得上";全没有 → `""`;`outline` 是坏 JSON → 跳过不报错。
- `normalize_outline`:带 `when` → 原样保留;不带 → `""`,不抛错。
- `outline_messages` 的输出含 `REALISM_RULE` 原文;最近章有 `when` 时含"最近几章的时间"。
- `work_order`:有 `when` → 含"本章时间:";没有 → 不含。
- `write_messages` 的输出含 `REALISM_RULE` 原文、**不含** `BOND_RULE` 原文;硬性要求仍是 1~9 连续(T005 的那个测试要继续通过)。
- 旧测试里如果断言了 `write_messages` 含伙伴关系那句话,改掉该断言并在报告里列出。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化。
2. `tests/test_structure.py` 通过。
3. 报告里贴出一次 `work_order(5, {...带 when 的章纲...})` 的完整输出。

## 这次不做

- 不做机械检查(比如数正文里"半夜"出现几次再打回)——分不清"有理由的夜戏"和"没理由的",先看提示够不够。
- 不记录"第几天"这种精确日历,只要相邻章接得上。
- 不部署、不在生产上试(架构方验收时在生产库副本上各写一章,看时间是否合理)。

## 审核记录

(架构方填)
