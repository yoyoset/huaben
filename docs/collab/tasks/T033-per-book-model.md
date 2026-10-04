# T033 每本书可以用自己的写作模型

依赖:T032(先合并 T032 再做)。

## 为什么

写作模型现在是全站一个(网页「设置」里的 `model`)。2026-10-04 给《阴差阳错》换 Muse 试写,《弄假成真》补货时也跟着用了 Muse;
反过来想让某一本回到 deepseek,只能全站一起换。用户 2026-10-05 同意做成每本书各用各的。

## 已定的方案

模型名存在这本书的写法设定里(`books.craft` 这段 JSON,不用迁移数据库);没填就用全站的。

### 1. `huaben/craft.py`

- `normalize_craft`:返回值里多一项 `"model"`——`str(d.get("model") or "").strip()[:80]`。
- `render_craft` 不显示它(它是按 `CATEGORIES` 循环的,本来就不会显示;确认一下 `notes` 那一行之外没有别的地方把整个 dict 打出来)。
- `options_view` 不动。

### 2. 客户端能"换一个模型再来一个"(`huaben/llm.py`)

`OpenRouterClient` 加方法:

```python
def with_model(self, model: str) -> "OpenRouterClient":
    """同一套密钥和地址、换一个模型名的客户端。同一个模型名只建一次(存在 self._siblings 里),共用 transport 与重试设置。
    model 为空或与当前模型相同 → 返回 self。"""
```

- 新客户端的配置 = 当前配置把 `llm_model` 换掉(`Settings` 是 pydantic 模型,用 `self._s.model_copy(update={"llm_model": model})`)。
- 构造新客户端时把当前的 `transport`、`retries`、`sleep` 原样传过去(所以 `__init__` 里要把 `transport` 也存到 `self._transport`)。
- `close()` 时把 `self._siblings` 里的也关掉。

**`llm.py` 现在 199 行,上限 200。** 先把 `build_payload` 和 `parse_response` 两个函数原样挪到新模块 `huaben/llm_chat.py`,
`llm.py` 里用 `from .llm_chat import build_payload, parse_response  # noqa: F401`(保留旧的导入路径,别处和测试的 `from huaben.llm import build_payload` 不用改)。
`llm_chat.py` 需要 `LLMResult`、`LLMError`、`LLMEmptyError`:这三个类留在 `llm.py`,为避免循环引用,
把它们挪到新模块 `huaben/llm_types.py`(连同 `LLM` 这个 Protocol),`llm.py` 和 `llm_chat.py` 都从那里引入,
`llm.py` 里同样 `from .llm_types import ...  # noqa: F401` 保留旧路径。`llm_responses.py` 里的引入可以不动。

### 3. 花费安全阀跟着换(`huaben/budget.py`)

`BudgetGuard` 加:

```python
def with_model(self, model: str):
    """里面的客户端支持换模型就换,并套上同样的安全阀;不支持(测试替身)就返回自己。"""
```

(新 `BudgetGuard` 用和自己一样的 `db_path`、上限参数;看 `BudgetGuard.__init__` 的参数照抄。)

### 4. 取"这本书该用的客户端"(新模块 `huaben/llm_pick.py`,纯函数)

```python
def for_book(llm, book: dict | None):
    """这本书的写法设定里填了 model、而且 llm 有 with_model 方法 → 返回换了模型的客户端;否则原样返回 llm。"""
```

用 `craft.from_book(book)["model"]` 取模型名。

### 5. 接线(`huaben/scheduler.py`)

`top_up`(给一本书补货的那个函数)一进来、拿到锁之后:`llm = for_book(llm, repo.get_book(conn, book_id))`,后面写章、封卷、开卷都用这个 `llm`。
只改这一处;开书对话、网页上的"测试连接"、导入卷剧本时的封卷都不改(仍用全站模型)。

### 6. 能看见(`huaben/api/routes_books.py` 或书详情所在的路由)

书详情接口(`GET /api/books/{id}`)的返回里加一项 `"model"`:这本书自己填的模型名,没填是空字符串。
(只加这一个字段;不改前端。)

改完每个 `.py` 仍须 ≤ 200 行。

## 测试(不碰网络)

1. `normalize_craft({"model": "  muse-spark-1.3-contributor  "})["model"] == "muse-spark-1.3-contributor"`;不填 → `""`;超过 80 字截断。
2. `render_craft({"model": "x-model"})` 的输出不含 `x-model`。
3. `OpenRouterClient.with_model`:用 `httpx.MockTransport`——原客户端模型 `deepseek-v4.1-flash`,`with_model("muse-spark-1.3-contributor")` 发出的请求走 `/responses`、
   请求体里的 `model` 是 muse;原客户端再发请求仍走 `/chat/completions`、`model` 是 deepseek。
   同一个名字调两次 `with_model` 返回同一个对象;传空字符串或当前模型名返回自己。
4. `BudgetGuard.with_model`:里面是 `OpenRouterClient` → 返回的是 `BudgetGuard`,里面的模型换了;里面是 FakeLLM(没有 `with_model`)→ 返回自己。
5. `for_book`:书的 craft 有 `model`、llm 有 `with_model` → 调用了 `with_model`(用一个记下参数的小替身);craft 没有 `model` → 原样;llm 没有 `with_model` → 原样;`book` 是 `None` → 原样。
6. `top_up`:两本书,一本 craft 里填了 `model="m2"`,一本没填;用一个带 `with_model` 的替身 LLM(记下每次 `chat` 时"当前模型名")跑一轮补货 →
   第一本的调用都记在 `m2` 上,第二本都记在默认模型上。
7. 书详情接口返回里有 `model` 字段。
8. `from huaben.llm import build_payload, parse_response, LLMResult, LLMError, LLMEmptyError, LLM, OpenRouterClient` 仍然可用。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数的变化。
2. `tests/test_structure.py` 通过。
3. 没在 craft 里填 `model` 的书,行为与改之前一样。

## 这次不做

- 不改前端(设置页、书页都不加输入框):模型名由架构方用现有的"改写法设定"接口填。
- 入账核对用的模型不单独设:和这本书的写作模型是同一个。
- 不做"每个步骤各用各的模型"。
- 不部署,不碰生产,不改 `stories/`。
