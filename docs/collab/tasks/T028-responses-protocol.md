# T028 写作模型:支持只走 Responses 接口的模型(Muse Spark)

依赖:无。

## 为什么

用户订的 OpenCode Go 里有 `muse-spark-1.3-contributor`,想用它写正文。它不支持话本现在用的 `/chat/completions`,
只支持 `/responses`。2026-10-04 在生产服务器上实测(带 `x-opencode-session` 头):

- `POST /chat/completions` → 400 `{"type":"error","error":{"type":"ModelProtocolUnsupported",...}}`
- `POST /responses` → 200,返回里 `status: "completed"`
- 不带后缀的 `muse-spark-1.3` 三种接口都是 `Model is unavailable`,不用管它。

它**关不掉思考**:`reasoning.effort` 发 `"none"` 被 400 拒绝(支持的值是 minimal / low / medium / high / xhigh / max),
不发时默认 high——两句话的回答烧了 1892 个思考 token,而且思考 token 算在 `max_output_tokens` 里;发 `"minimal"` 时是 126 个。

## 已定的方案

### 1. 新模块 `huaben/llm_responses.py`(纯函数,不发请求)

`huaben/llm.py` 已经 198 行,新逻辑一律放新模块,`llm.py` 只加分支。

```python
THINK_ROOM = 2000  # 思考 token 算在 max_output_tokens 里,给它留的余量

def uses_responses(model: str) -> bool:
    """这个模型是不是只能走 /responses。目前只有 Muse 一家:模型名以 "muse-" 开头。"""

def build_responses_payload(model, messages, *, max_tokens, temperature, json_mode=False) -> dict:
    ...

def parse_responses(data: dict, duration_ms: int) -> LLMResult:
    ...
```

`build_responses_payload` 返回(字段名照抄,不要多发别的字段,尤其不要发 `frequency_penalty` / `presence_penalty` / `reasoning_effort`):

```json
{
  "model": "<model>",
  "input": <messages 原样,role 与 content 不改>,
  "max_output_tokens": <max_tokens + THINK_ROOM>,
  "temperature": <temperature>,
  "reasoning": {"effort": "minimal"}
}
```

`json_mode=True` 时再加一项:`"text": {"format": {"type": "json_object"}}`。

`parse_responses` 按下面这个实测到的返回取值:

```json
{
  "status": "completed",
  "incomplete_details": null,
  "output": [
    {"type": "reasoning", "status": "completed", "encrypted_content": "…", "summary": []},
    {"type": "message", "role": "assistant",
     "content": [{"type": "output_text", "text": "正文在这里", "annotations": [], "logprobs": []}]}
  ],
  "usage": {"input_tokens": 45, "output_tokens": 199, "total_tokens": 244,
            "output_tokens_details": {"reasoning_tokens": 126}}
}
```

- 正文 = `output` 里所有 `type == "message"` 的项,其 `content` 里所有 `type == "output_text"` 的 `text`,按顺序接起来。别的项(`reasoning`)跳过。
- `tokens_in = usage.input_tokens`,`tokens_out = usage.output_tokens`,`cost_usd = 0.0`,`provider = ""`。
- `truncated = (status == "incomplete" 且 incomplete_details.reason == "max_output_tokens")`。
- 正文去掉空白后为空 → 抛 `LLMEmptyError`,参数顺序和 `parse_response` 里那一处一样,消息写
  `f"empty content (status={status}, output_tokens={tout})"`。(实测:思考把额度用光时就是 `output: []`、`status: "incomplete"`。)
- `data` 不是 dict,或 `output` 不是列表 → 抛 `LLMError(f"unexpected response shape: {data!r}"[:500])`。

`LLMResult` / `LLMError` / `LLMEmptyError` 从 `huaben/llm.py` 引入。**`llm.py` 要用新模块里的函数,为避免循环引用,在 `OpenRouterClient.chat` 函数体内部 `from .llm_responses import ...`,不要写在 `llm.py` 文件顶部。**

### 2. `huaben/llm.py` 的 `OpenRouterClient.chat`

只改三处,其余(重试、总时长上限、空正文计费累加、`x-opencode-session` 头)原样共用:

- 开头:`responses = uses_responses(self._s.llm_model)`;是的话 `payload = build_responses_payload(...)`(同样的 `max_tokens or self._s.chapter_max_tokens`、`temperature`、`json_mode`),否则照旧 `build_payload(...)`。
- 发请求的路径:`"/responses" if responses else "/chat/completions"`。
- 解析:`parse_responses(data, 耗时)` 或照旧 `parse_response(data, 耗时)`。

改完 `llm.py` 仍须 ≤ 200 行;超了就把这三处收成 `llm_responses.py` 里的一个小函数(比如返回 `(路径, payload, 解析函数)`),不要调高上限。

## 测试(新文件 `tests/test_llm_responses.py`,不碰网络)

1. `uses_responses`:`"muse-spark-1.3-contributor"` → True;`"deepseek-v4.1-flash"`、`"mimo-v2.6-flash"`、`"deepseek/deepseek-v4.1-flash"` → False。
2. `build_responses_payload("muse-spark-1.3-contributor", msgs, max_tokens=6000, temperature=0.9)`:
   `input` 就是 `msgs`;`max_output_tokens == 8000`;`reasoning == {"effort": "minimal"}`;键里没有 `messages`、`max_tokens`、`frequency_penalty`、`presence_penalty`、`reasoning_effort`、`text`。
3. `json_mode=True` → `text == {"format": {"type": "json_object"}}`。
4. `parse_responses`:用上面那段实测返回 → `text == "正文在这里"`,`tokens_in == 45`,`tokens_out == 199`,`truncated is False`。
5. 两个 `message` 项、其中一个有两段 `output_text` → 三段按顺序接起来。
6. `{"status":"incomplete","incomplete_details":{"reason":"max_output_tokens"},"output":[],"usage":{"input_tokens":58,"output_tokens":2000}}` → 抛 `LLMEmptyError`,且异常上的 `tokens_out == 2000`。
7. `status: "incomplete"`、原因 `max_output_tokens`、但 `output` 里有正文 → 不抛,`truncated is True`。
8. `parse_responses("oops", 0)` → 抛 `LLMError`。
9. 客户端走对了路:照 `tests/test_llm.py` 里用 `httpx.MockTransport` 的写法,模型设成 `muse-spark-1.3-contributor`,
   断言请求的路径以 `/responses` 结尾、请求体里有 `input` 没有 `messages`、请求头带 `x-opencode-session`,返回的 `LLMResult.text` 正确。
10. 模型是 `deepseek-v4.1-flash` 时,路径仍以 `/chat/completions` 结尾(现有测试原样通过即可,另加这一条断言)。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数从多少变成多少。
2. `tests/test_structure.py` 通过(单文件 ≤ 200 行)。
3. `git diff --stat` 只动了 `huaben/llm.py`、`huaben/llm_responses.py`、`tests/test_llm_responses.py`(以及协作文档)。

## 这次不做

- 不改设置页的模型列表、不改预设。模型名由用户在设置页手填或架构方用接口改。
- 不做流式。不解析、不保存思考内容。
- 不给别的模型改思考档位;`deepseek`、`mimo` 照旧走 `/chat/completions`。
- 不部署,不碰生产。

## 审核记录

通过 2026-10-04。架构方自己重跑:`python -m pytest -q` 517 全过(原 507)。读了 diff:`llm.py` 只改三处(取 路径/请求体/解析函数、发请求的路径、解析),199 行;
`llm_responses.py` 的字段与卡一致,循环引用按卡在函数体内导入。
