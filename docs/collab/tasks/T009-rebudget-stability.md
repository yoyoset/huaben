# T009 节奏:补预算的判断要稳,2 章的节拍别叫"重头戏"

## 为什么

架构方验收 T004 时对《杂役仙尊》执行了两次"重排本卷节奏",模型两次的判断不一样:
一次说"已走完 5 个节拍"(对),一次说"已走完 7 个"(错——第 6、7 个节拍"处理丹房纠纷""小比前夕"根本还没写),
后一次会让故事直接跳过两个节拍。原因:`_ask` 固定用 `temperature=0.7`,那是给"规划"用的;"对照摘要判断走到哪了"是判断题,应该用低温度。
另外接口只返回预算,不返回模型判断的"已走完几个节拍",出了错人看不出来。

顺带:`beat_line` 对"共 2 章"的节拍也说"是重头戏……慢下来把这场戏写足",而卷规划的规则里 2 章是普通节拍、3 章以上才是重头戏。

## 改哪些文件

### 1. `huaben/pipeline/volume.py` 的 `_ask`

加一个参数 `temperature: float = 0.7`,传给 `call_step`(原来写死的 0.7 换成这个参数)。其它调用方不用改。

### 2. `huaben/pipeline/rebudget.py`

- 调 `_ask` 时传 `temperature=0.2`。
- `parse` 改成返回 `(budget, done_beats)`;`rebudget` 的返回值多一项 `"done_beats": done_beats`。
- 写库之后加一条运行记录:`repo.log_run(conn, book_id, "volume_budget", note=f"已走完 {done_beats} 个节拍;预算 {budget};总章数 {旧值}→{新值}")`。

### 3. `huaben/beat_budget.py` 的 `beat_line`

最后一个分支(`k < n`)按 `n` 分开,文字照抄:

```python
    if n == 2:
        return (f"节奏:{head}共 2 章,本章是第 1 章——正常推进,把这个节拍走到一半以上;"
                f"本章必须有一个上一章没有的实质进展(局面、信息或关系变了),不要把上一章的事再演一遍。")
    return (f"节奏:{head}是重头戏,共 {n} 章,本章是第 {k} 章——慢下来把这场戏写足;"
            f"但本章必须有一个上一章没有的实质进展(局面、信息或关系变了),不要把上一章的事再演一遍。")
```

### 4. 测试

- `beat_line(["a","b"], 1, 1, 2)`:含"共 2 章"和"正常推进",**不含**"重头戏"。`beat_line(["a","b"], 1, 1, 3)` 仍含"重头戏"。
- `rebudget` 的返回值含 `done_beats`;用能记录调用参数的替身 LLM(看 `tests/` 里现有替身怎么记录 `temperature`,没有就在测试里包一层)断言这次调用的 `temperature == 0.2`。
- 卷规划(`plan_volume`)那次调用的温度仍是 0.7。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化。
2. `python -c "from huaben.beat_budget import beat_line; print(beat_line(['a','b'],1,1,2)); print(beat_line(['a','b'],1,1,3))"` 的输出贴进报告。

## 这次不做

- 不做"多问几次取多数"之类的投票;先看低温度够不够稳。

## 审核记录

(架构方填)
