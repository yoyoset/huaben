# T031 设定类的要求也分级:能力要求分三档、写法设定是"基调"不是"每章定额"、每章可以有自己的字数

依赖:T030(已通过)。

## 为什么

用户 2026-10-05:"除了这些还有写作规则里面的,设定选项、世界、能力,各种设定的一刀切问题。"
架构方过了一遍,对**现在在写的书**(都是剧本书)真正起作用的一刀切有三处:

1. **招牌能力**:`SIGNATURE_RULE`("反复出场的人物靠自己的招牌能力解决问题……不要让配角只是没有能力的工具人")对每本书、每一章都发。
   它是给战斗流写的;《阴差阳错》是感情线为主的志异,茶馆东家、更婶这样的常驻配角不需要"招牌能力"。
2. **写法设定被说成"全书遵守"的定额**:想象力选"大开脑洞"时,每章的提示里都有"每章都要有一样读者没见过的东西"——
   一章过节吃月饼的日常也被要求塞一样新东西。
3. **字数全站一个数**(`chapter_words`,默认 2500):日常章和大高潮一样长;篇幅底线(目标的四成)也跟着这一个数。

## 已定的方案

### 1. 写法设定加一项"能力与战斗"(`huaben/craft.py`)

`CATEGORIES` 末尾加(顺序放在 `pacing` 之后):

```python
"power": ("能力与战斗", {
    "core": ("核心看点", "能力和对决是这本书的主菜:重要人物各有招牌能力,有名字、有规则、有代价,会进阶"),
    "light": ("点到为止", "本事是人物的一部分,不是主菜:各人的本事前后一致就行,不必人人有招牌、不必回回进阶"),
    "none": ("不写", "这本书不靠能力和打斗推进"),
}),
```

`DEFAULT["power"] = "core"`(= 现在的行为)。`normalize_craft` / `render_craft` / `options_view` 都是按 `CATEGORIES` 循环的,不用另改;
设置页的选项是从 `options_view` 来的,会自己多出这一项(不用改前端;如果前端把五项写死了,报告里说明,不要自己改前端)。

### 2. 招牌能力的要求按这一档给(`huaben/pipeline/rules.py`)

加函数:

```python
SIGNATURE_LIGHT = "各人的本事前后一致,不要临时冒出万能的新能力来解围。"

def signature_rule(craft: dict) -> str:
    """招牌能力的要求按书的"能力与战斗"档给:core = SIGNATURE_RULE;light = SIGNATURE_LIGHT;none = 空字符串。craft 是 normalize_craft 之后的。"""
```

`huaben/pipeline/prompts.py`:

- `write_messages` 的【尽量做到】里,`"- " + SIGNATURE_RULE + "\n"` 那一行换成:`signature_rule(from_book(ctx.book))` 非空才加 `"- " + 它 + "\n"`,为空就没有这一行。
- `outline_messages`(第 83 行附近那一长串)里的 `{SIGNATURE_RULE}` 同样换成 `signature_rule(from_book(ctx.book))`(为空时不要留下空行)。
- 入账提示(`ledger_messages`)里登记 signature 的那句不改。

### 3. 写法设定是基调(`huaben/craft.py`)

- `render_craft` 的标题从 `【写法设定(读者选定,全书遵守)】` 改成 `【写法设定(全书的基调;具体到这一章,以工单为准)】`。
- `CATEGORIES["imagination"]["wild"]` 说明的最后一句
  `每章都要有一样读者没见过的东西,写成可感的画面而不是解释,并且改变人物的处境`
  改成
  `多数章里要有一样读者没见过的东西,写成可感的画面而不是解释,并且改变人物的处境;日常和过渡的章不必硬塞`。
- `NOVELTY_RULE["wild"]` 里的 `novelty 必填:每章都要有一样读者没见过的东西,` 改成 `novelty 多数章要填(日常、过渡的章可以空):填的时候要有一样读者没见过的东西,`,后半句不动。

### 4. 每章可以有自己的字数

- `huaben/pipeline/normalize.py` 的 `normalize_outline`:加 `"words"`——章纲里的 `words` 是 800~8000 之间的整数就原样保留,否则为 `0`
  (`bool` 不算整数;字符串形式的数字如 `"2000"` 也接受)。
- `huaben/grip.py` 加:

  ```python
  def words_of(outline: dict, default: int) -> int:
      """这一章的目标字数:章纲填了 words 就用它,否则用全站的 default。"""
  ```

- `huaben/pipeline/chapter.py` 的 `_draft_until_accepted`:里面两处 `settings.chapter_words`(传给 `prompts.write_messages` 的、传给 `draft_problems` 的)
  都换成 `words_of(outline, settings.chapter_words)`。`_imported_text` 里那一处不改。
  **`chapter.py` 现在 198 行,上限 200**:在函数开头算一次存进局部变量会多一行,不行就内联;要是怎么写都超,把 `fatal`/`heavy` 那几行的拼装挪成 `grip.py` 或 `draft_check.py` 里的一个函数,不要调高上限。
- `huaben/rhythm.py` 的 `rhythm_problems`:某章填了 `words` 但不是 800~8000 的整数 → `第 N 章 words 必须是 800~8000 的整数(可不填)`。

## 测试

1. `normalize_craft({})["power"] == "core"`;`{"power": "light"}` 保留;`{"power": "乱填"}` → `"core"`。
2. `render_craft` 的输出含 `能力与战斗`,标题含 `全书的基调`,不含 `全书遵守`。
3. `signature_rule`:core → 等于 `SIGNATURE_RULE`;light → 等于 `SIGNATURE_LIGHT`;none → `""`。
4. `write_messages`:书的 craft 是 `power="none"` → 提示里不含 `招牌能力`;`"light"` → 含 `各人的本事前后一致`、不含 `工具人`;不填 → 含 `工具人`(现状)。
5. `outline_messages`:`power="none"` → 不含 `SIGNATURE_RULE` 的文字,且没有连续两个以上的空行。
6. `CATEGORIES["imagination"]["wild"]` 的说明含 `日常和过渡的章不必硬塞`;`novelty_rule({"imagination":"wild"})` 含 `可以空`。
7. `normalize_outline`:`words=2000` → 2000;`"2000"` → 2000;`500`、`9000`、`True`、`"多"`、不填 → 0。
8. `words_of({"words": 1800}, 2500) == 1800`;`words_of({}, 2500) == 2500`;`words_of({"words": 0}, 2500) == 2500`。
9. 流水线:章纲 `words=1200`、全站 2500,正文 600 字(够 1200 的四成、不够 2500 的四成)→ 不因篇幅打回;写作提示里是 `约 1200 字`。
10. `rhythm_problems`:`words=500` 报问题;`words=2000`、不填不报。

现有测试里断言旧标题(`全书遵守`)或旧句子的,改成新的文字。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数从 540 变成多少。
2. `tests/test_structure.py` 通过。
3. craft 里没有 `power`、章纲里没有 `words` 的书:除了写法设定的标题和"大开脑洞"那两句话变了,行为与改之前一样。

## 这次不做

- 不动模型自己规划的那条路上的一刀切(卷规划必须有对手/谷底/代价、世界坐标只升不降、世界观必须有力量机制和三个地方、长期对手每卷必须变化、开篇三章规则):
  现在生产上没有这种书,等有了再分级。架构方已记在 `BUILD_LOG.md`。
- 不做"每本书用自己的写作模型"(现在是全站一个):要动后台线程拿模型的方式,另出卡。
- 不做一章埋多条伏笔。
- 不部署,不碰生产,不改 `stories/`、不改前端。
