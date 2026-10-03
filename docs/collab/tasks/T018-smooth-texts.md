# T018 接句工具:把切碎的正文逐章交给写作模型接顺,逐章核对

依赖:T017(要用 `comma_density`)。

## 为什么

《弄假成真》第 12~30 章的正文被逗号切碎了(见 T017)。架构方已经实测(2026-10-03):把一章原文配一份"只接断句"的系统提示词
交给 `deepseek-v4.1-flash`,**每章单独一次调用、互相看不见**,约 20 秒一章:

| | 第 19 章 | 第 30 章 |
|---|---|---|
| 每百字逗号 | 10.7 → 8.9 | 12.4 → 7.6 |
| 去掉标点后与原文的相似度 | 1.000 | 0.998 |
| 章纲原话 | 全在 | 全在 |

用本卡定稿的提示词(`T018-system-prompt.txt`,比上表那版更严:一个字都不许动)又实测了一次:第 19 章 10.7 → 8.7,第 30 章 12.4 → 8.9,
相似度都是 1.000,原话全在,段数不变。也就是**一遍只能到 8.8 左右,到不了 8.5**——所以下面的流程带着"还是太碎"的反馈再改一两遍;
带反馈重改这一步还没有对真实模型试过,到不了就按 `still_choppy` 交回密度最低的一稿,由架构方看。

它只动标点,不动情节。所以返工交给它做,再用机械检查兜底。这张卡把那次手工试验做成一个能重复跑的命令。
试验的原稿、改稿、提示词在 `stories/弄假成真/text/` 与 `stories/弄假成真/text-ds-trial/`(只读参考,不要改)。

## 已定的方案

### 1. 纯函数(新建 `huaben/smooth.py`)

```python
SMOOTH_TARGET = 8.5      # 改完后每百字逗号数不超过它才算接顺
MIN_SIMILARITY = 0.995   # 去掉标点与空白后,改稿与原稿的相似度下限
MAX_PARA_DRIFT = 0.02    # 段数允许的相对偏差


def strip_punct(text: str) -> str:
    """去掉所有空白与标点(中文、英文标点和各种引号、省略号、破折号),只留字。"""


def smooth_messages(body: str, lines: list[str], feedback: list[str]) -> list[dict]:
    """[system, user]。user = 下面的"用户消息"格式。"""


def smooth_problems(old: str, new: str, lines: list[str]) -> list[str]:
    """改稿不能用的理由(硬伤);空列表 = 可以用。只查硬伤,不查逗号密度。"""
```

`smooth_problems` 按顺序查,全部查完一起返回:

1. `difflib.SequenceMatcher(None, strip_punct(old), strip_punct(new), autojunk=False).ratio() < MIN_SIMILARITY`
   → `改动了文字(相似度 {r:.3f}):只许改标点和断句,不许增删改任何字词。`
2. `huaben.verbatim.missing_lines(new, lines)` 非空 → 每句一条:`这句原话被改了,必须一字一标点照原样:{句子}`
3. 段数(按 `[p for p in text.split("\n") if p.strip()]` 数)相对偏差超过 `MAX_PARA_DRIFT`
   → `段数变了({a} → {b}):不许合并或拆分段落。`
4. `new` 的非空白字数不到 `old` 的 90% → `稿子不完整(只有原文的 {p}%),必须从第一句改到最后一句。`

系统提示词:原文在 `docs/collab/tasks/T018-system-prompt.txt`(全角标点、中文弯引号)。把它**一字不改**地抄进 `smooth.py` 作为常量 `SYSTEM`
(不含文件末尾那个换行);`tests/test_smooth.py` 里加一条断言:`SYSTEM == 那个文件的内容.rstrip("
")`,抄错了测试就红。

用户消息格式(`lines` 为空就没有第一块;`feedback` 为空就没有第二块):

```
不许动的原话:
- {原话1}
- {原话2}

上一稿的问题,这一稿必须改掉:
- {问题1}

下面是要改的正文:

{body}
```

### 2. 逐章执行(新建 `huaben/smooth_run.py`)

```python
def smooth_chapter(llm, body: str, lines: list[str], attempts: int = 3) -> dict:
    """返回 {"text": 最终稿, "status": "ok" | "still_choppy" | "kept_original", "before": 密度, "after": 密度, "tries": 次数, "notes": [...]}"""
```

- 原稿密度已经 ≤ `SMOOTH_TARGET`:不调模型,`status="ok"`,`text` 为原稿,`tries=0`。
- 每次调用:`llm.chat(smooth_messages(body, lines, feedback), max_tokens=12000, temperature=0.3)`;**每次都从原稿 `body` 改,不拿上一稿接着改**。
  结果被截断(`truncated`)按硬伤算,`feedback = ["上一稿没有写完,必须从第一句改到最后一句。"]`。
- 有硬伤(`smooth_problems` 非空):`feedback = 这些硬伤`,再来一次。
- 没硬伤但密度仍 > `SMOOTH_TARGET`:记下这一稿(只保留密度最低的一稿),
  `feedback = [f"还是太碎(每百字 {d:.1f} 个逗号,要降到 8 以下):把剩下的主谓之间、状语后面的逗号继续去掉。"]`,再来一次。
- 没硬伤且密度 ≤ `SMOOTH_TARGET`:立刻返回 `ok`。
- 用完次数:有"没硬伤"的稿 → 返回密度最低的那一稿,`still_choppy`;一稿都没有 → 返回原稿,`kept_original`。
- 章与章之间不共享任何东西:`smooth_chapter` 只接收这一章的正文和原话。

### 3. 命令行(新建 `huaben/smooth_cli.py`,`python -m huaben.smooth_cli`)

```
python -m huaben.smooth_cli --src <目录> --out <目录> --volume <vol.json> [--from 12] [--to 30]
```

- `--src` 下的 `NN.txt`(两位章号)逐个读;`--volume` 是卷剧本 json,第 N 章的原话取 `chapters[N-1]["lines"]`(没有就空列表)。
- 不在 `--from`~`--to` 范围内的章:原样复制到 `--out`。
- 范围内的章:`smooth_chapter` → 写 `--out/NN.txt`(UTF-8,末尾一个换行)。**绝不写回 `--src`**;`--out` 与 `--src` 是同一个目录就报错退出。
- 全部跑完写 `--out/report.json`(每章的 status / before / after / tries / notes),并在屏幕上逐章打印一行。
- 模型客户端:照 `huaben/api/deps.py` 的 `llm_settings` 的办法取实际生效的配置(`effective(get_settings(), repo.get_app_settings(conn))`),
  `OpenRouterClient(st)`。把"建客户端"写成一个小函数,测试里用替身替掉。

### 4. 测试(新建 `tests/test_smooth.py`,全部用替身,不碰网络)

- `strip_punct`:`"他的手，停了。"` 与 `"他的手停了。"` 结果相同。
- `smooth_problems`:只去逗号 → 空;换了一个词(文本足够长,使相似度 < 0.995)→ 有"改动了文字";原话被改 → 有"这句原话被改了";
  合并了一半的段 → 有"段数变了";只返回前半篇 → 有"稿子不完整"。
- `smooth_messages`:system 是 `SYSTEM`;user 里含原话清单与正文;没有 lines、没有 feedback 时那两块不出现。
- `smooth_chapter`(替身 LLM 按次序吐回复):
  - 原稿密度低 → 不调用模型;
  - 第一稿就合格 → `ok`,`tries=1`;
  - 第一稿改了字、第二稿合格 → `ok`,`tries=2`,第二次调用的 user 消息里带着第一稿的问题;
  - 三稿都没硬伤但都偏碎 → `still_choppy`,返回密度最低的一稿;
  - 三稿都有硬伤 → `kept_original`,`text` 等于原稿;
  - 第二次调用的正文仍是原稿(不是第一稿)。
- 命令行(临时目录,替身客户端):范围外的章原样复制;范围内的章写了新稿;`report.json` 存在且条目数对;`--out` 等于 `--src` → 非 0 退出、不写任何文件。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化。
2. `tests/test_structure.py` 通过(三个新文件各 ≤ 200 行)。
3. 报告贴出 `python -m huaben.smooth_cli --help` 的真实输出。
4. **不要对真实模型跑**(没有密钥,硬规则 5)。对《弄假成真》的实跑由架构方验收后在生产容器里做;报告"没有实测的部分"照实写。

## 这次不做

- 不删"一动不动""一级一级"这类口头禅(那要改字,和"只动标点"的核对冲突;架构方另行处理)。
- 不做接口、不做前端、不自动导入生产。
- 不改 `stories/` 下的任何文件。

## 审核记录

通过 2026-10-03。架构方自己重跑:`python -m pytest -q` 496 全过;`python -m huaben.smooth_cli --help` 正常;三个新文件 70/32/57 行。
读了全部代码:四条硬伤的顺序与原文、每次都从原稿改、只留密度最低的无硬伤稿、`--out` 等于 `--src` 退出码 2 且不写文件、`SYSTEM` 与提示词文件有测试钉住相等,都与方案一致。
报告里"全删逗号的好稿会触发稿子不完整"的发现是对的,也说明 90% 这条线不会误伤真实改稿(实测真实改稿字数 96%~98%)。对真实模型的实跑由架构方在生产容器里做,结果另记。
