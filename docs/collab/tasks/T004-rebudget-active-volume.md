# T004 节奏:给已经在写的卷补章数预算

依赖:T003 通过。

## 为什么

T003 只对**新规划的卷**生效。用户现在在读的三本书都在第 1 卷中途,不补预算就要等几十章后换卷才有改善。
做法照搬"给旧卷补征战结构"(`fill_arc`,`huaben/pipeline/volume.py`):一个显式触发的接口,一次模型调用,不放在写章路径上。

## 已定的方案

让编辑看"本卷节拍 + 已写各章摘要",回答两件事:**已经走完了几个节拍**、**剩下每个节拍各给几章**。
程序把它拼成完整的 `beat_chapters`,并把卷的总章数改成新的和。

### 1. 新建 `huaben/pipeline/rebudget.py`

纯函数(照抄):

```python
def merge_budget(done_beats, remaining, beat_count: int, volume_done: int) -> list[int] | None:
    """已走完的节拍数 + 剩下每个节拍的章数 → 完整的 beat_chapters;形状不对返回 None。
    已走完的节拍把已写的 volume_done 章平摊掉(它们只用来让 locate 跳过去,具体怎么摊不影响以后);
    一个节拍都没走完时,已写的章都算在第一个节拍头上。"""
    if isinstance(done_beats, bool) or not isinstance(done_beats, int) or not 0 <= done_beats < beat_count:
        return None
    rest = normalize_budget(remaining, beat_count - done_beats)
    if rest is None:
        return None
    if done_beats == 0:
        return [rest[0] + volume_done, *rest[1:]]
    base, extra = divmod(volume_done, done_beats)
    return [base + (1 if j < extra else 0) for j in range(done_beats)] + rest
```

以及 `rebudget(conn, llm, settings, book_id) -> dict`,结构照抄 `fill_arc`:
取进行中的卷(没有就抛 `ChapterFailed("这本书没有进行中的卷", step="volume")`)→ 取本卷已写章摘要 →
调模型(步骤名 `"volume_budget"`,复用 `volume.py` 里的 `_ask`)→ `merge_budget`,返回 None 就抛 `ParseError("节拍预算形状不对")`(让 `_ask` 重试一次)
→ `repo.set_volume_budget(conn, volume["id"], budget, sum(budget))` → 返回 `{"beat_chapters": budget, "target_chapters": sum(budget)}`。

### 2. 提示词(`huaben/pipeline/volume_prompts.py`,新增函数 `budget_messages(volume, summaries)`,原文照抄)

system 用文件里已有的 `_SYSTEM`。user:

```
【本卷(第{idx}卷)目标】{goal}
【本卷节拍】
{编号列表,同 arc_messages 的写法}

【本卷已写章节】
{summaries,每章一行;没有就写"(还没有)"}

这一卷已经写了 {n} 章。请对照节拍判断:已经完整走完了前几个节拍(done_beats,没有走完的那个不算);
然后给剩下的每个节拍分配还需要几章(remaining,按顺序,第一个是正在进行的那个节拍还需要几章)。
{BUDGET_RULE}
已经拖得太久的节拍,remaining 里只给 1 章,让它下一章就收掉。
只输出如下结构的 JSON:
{"done_beats": 已完整走完的节拍数(整数), "remaining": [剩下每个节拍还需要几章(整数)]}
```

(`BUDGET_RULE` 里"target_chapters 等于……"那半句在这里多余但无害,照用,不要另写一份。)

如果 `volume_prompts.py` 加完超过 200 行,把 `budget_messages` 放进 `rebudget.py`。

### 3. 仓库与接口

- `huaben/repo/volumes.py` 新增:
  ```python
  def set_volume_budget(conn, volume_id: int, beat_chapters: list[int], target_chapters: int) -> None:
  ```
  一条 UPDATE 同时写 `beat_chapters` 和 `target_chapters`,然后 commit(照 `set_volume_arc`)。
- `huaben/api/routes_craft.py`:在 `volume_arc` 下面照样加
  `POST /api/books/{book_id}/volume/budget` → `rebudget(...)`,异常处理与 `volume_arc` 完全一致。
- 前端:在 `web/` 里搜 `volume/arc`。**如果**有调用它的按钮,在旁边照同样的写法加一个「重排本卷节奏」按钮,调新接口,
  成功后提示"本卷改为 N 章,下一章起生效";**如果没有**,只做接口,不做界面,并在报告里说明。

### 4. 测试

- `merge_budget`:
  | 输入 | 期望 |
  |---|---|
  | `(0, [1,3,2], 3, 4)` | `[5,3,2]` |
  | `(2, [3], 3, 5)` | `[3,2,3]` |
  | `(2, [3], 3, 1)`(章比节拍少) | `[1,0,3]` |
  | `(3, [], 3, 5)`(全走完了不合法) | `None` |
  | `(1, [3], 3, 5)`(长度不对) | `None` |
  | `("1", [3,2], 3, 5)` | `None` |
- 对每个非 None 的结果再断言:`sum(结果) == volume_done + sum(remaining 夹到 1..8 之后)`,
  且 `locate(结果, volume_done)[0] == done_beats + 1`(从正在进行的那个节拍接着走)。
- `rebudget` 端到端:照 `tests/test_arc.py` 里 `test_fill_arc_upgrades_an_existing_volume` 的写法,用剧本 LLM,
  断言卷的 `beat_chapters` 和 `target_chapters` 都被更新;没有进行中的卷时抛 `ChapterFailed`。
- 接口:POST 返回 200 和两个字段;模型输出坏 JSON 两次 → 502。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化。
2. `tests/test_structure.py` 通过。
3. 报告里贴出 `budget_messages` 对一个 3 节拍、已写 4 章的假卷渲染出来的完整 user 文本(用 python -c 打印),
   供架构方核对提示词与卡里原文一致。

## 这次不做

- 不自动触发(不放进写章路径;由用户或架构方对每本书手动点一次)。
- 不对生产上的三本书执行(架构方验收后在生产上做,并把前后预算给用户看)。
- 不改已经写好的章。

## 审核记录

(架构方填)
