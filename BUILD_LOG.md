# 构建日志

按 loop 轮次追加。记录:做了什么 / 踩的坑(含"最初以为 A,实测是 B") / 已知但暂不处理的问题。
范围依据 `docs/v0-scope.md`;不部署到 13、不做对外操作。

## 路线(切片顺序)

1. [x] 脚手架 + 配置 + SQLite schema + repo 层
2. [x] LLM 客户端(OpenRouter,关思考、惩罚=0、记 token/耗时/费用;可注入 fake 以便测试)
3. [x] 分层记忆(取数 context.py + 渲染 render.py);各步骤的指令 prompt 放到切片 4 与流水线一起做
4. [x] 章节流水线:章纲 → 正文 → 入账+核对(打回重写)
5. [x] 卷规划 + 封卷
6. [x] 预生成缓冲调度
7. [ ] 保底 TTS(edge-tts → MP3)
8. [ ] FastAPI 路由 + 开书对话
9. [ ] PWA 前端(书架/阅读/播放器/Media Session/睡眠定时)
10. [ ] Dockerfile + docker-compose + 备份脚本(仅文件,不部署)

## 轮 1 — 脚手架 + 数据层

做了:`huaben/config.py`(pydantic-settings,`HUABEN_*`)、`huaben/db.py`(schema:书/圣经/卷/章/账本三表/pipeline_runs/audio)、
`huaben/repo.py`(唯一的 SQL 入口)、`tests/test_repo.py`(8 个,内存库,全绿)。

决策:
- 标准库 sqlite3,不上 ORM:表少、查询简单。列表类字段存 JSON 文本。
- `pipeline_runs` 表一开始就建,v0 验收要"单章平均成本与耗时",`repo.cost_summary` 直接出。
- `read_pos` 放在 books 上,`buffered_ahead` 以它为基准算缓冲余量。

踩坑:
- git bash 里一次塞多个含中文的大 heredoc 会整条命令解析失败且**零文件写入**;大文件改用 Write 工具。

暂不处理:
- 没有迁移机制(schema 用 `CREATE TABLE IF NOT EXISTS`);v0 改表结构时手动处理,有真实数据后再加。
- 每个 repo 函数各自 commit,没有跨函数事务;流水线"入账"一步需要原子性时用 `db.tx`(下一批切片处理)。

## 轮 2 — LLM 客户端

做了:`huaben/llm.py`:`OpenRouterClient`(httpx,可注入 transport)、`build_payload`/`parse_response` 纯函数、`FakeLLM`(后续流水线测试用)、
10 个测试(MockTransport,不碰网络)。总计 18 个测试全绿。

决策:
- payload 固化前身踩坑结论:两项惩罚=0、`reasoning.effort="none"`、`usage.include=true`(取 `usage.cost` 作真实费用)。
- 200 但正文空 → `LLMEmptyError` 并重试;`finish_reason=length` → `LLMResult.truncated=True` 交给上层决定(不静默吞)。
- 重试只针对网络错误/408/429/5xx/空正文;4xx 直接抛(鉴权/参数错重试无意义)。

**未实测(待用户提供密钥)**:payload 字段(尤其 `reasoning.effort="none"` 与 `usage.include` 在
`deepseek/deepseek-v4.1-flash` 上是否被接受、`usage.cost` 是否真的返回)只靠 MockTransport 验证了"我们发了什么",
没验证"OpenRouter 实际怎么回"。已记 Magpie 待办:配置密钥后跑一次 smoke test。

## 轮 3 — 分层记忆 + 工程纪律重构

用户中途补充要求:按专业项目管理 + 第一性原理,注意单一职责、可读性、可扩展性、单文件不无限增长。已写入项目 `CLAUDE.md` "工程约定"并存为 memory。

重构(先于新功能,因为 `repo.py` 已 215 行、混了五类职责):
- `repo.py` → `repo/` 包(books / volumes / chapters / ledger / runs),对外 `repo.xxx` 不变。
- `schema.py` 从 `db.py` 独立;`llm_fake.py` 从 `llm.py` 独立(测试替身不属于生产客户端)。
- `tests/test_structure.py`:单文件 ≤200 行,超了就测试失败 —— 用机制而不是自觉来守这条约定。

做了:`context.py`(`load_context` 读库 → `StoryContext`;`select_ledger` 纯函数)、`render.py`(梗概→往卷→本卷目标→本卷章摘要→账本→最近原文,纯函数)。
28 个测试全绿。

决策:
- 核心人物每章必带;非核心人物只在章纲提到名字时带;**已死亡人物保留**(否则模型让死人复活)。前身踩坑"关键词触发 → 名字漂移"的直接应用。
- 世界事实只带最近 40 条,避免账本把 prompt 撑大(第 500 章 ≈ 第 50 章体量的前提)。
- 本卷章摘要排除"最近原文"已带的章,避免同一章摘要+原文重复占 token。

暂不处理:
- 非核心人物"章纲没提名字但剧情会碰到"的漏选风险(编辑·章纲会在工单里列出出场人物,靠这个兜;若实测漏选再加规则)。
- 40 条事实的上限是拍的数,没有实测依据;有真实账本后按 token 用量调。

## 轮 4 — 章节流水线

做了:`pipeline/` 包,按职责拆四个文件:`prompts.py`(三步指令,纯函数)、`parsing.py`(JSON 解析校验)、
`ledger_apply.py`(原子入账)、`chapter.py`(编排 `generate_chapter`)。11 个流水线测试,全库 39 个全绿,全程 FakeLLM,未碰网络。

决策:
- **入账原子**:repo 写函数加 `commit=False` 选项,`apply_ledger` 在 `db.tx` 里一次写完;被打回的稿子**不入账**(测试覆盖)。
- **失败显式**:章纲两次解析失败 / 写满 `max_write_attempts` 稿仍冲突 → `ChapterFailed`,章标 failed,原因进 `pipeline_runs`。
- **序号无空洞**:`next_chapter_idx` 只数 accepted;每次生成前 `discard_unaccepted` 清掉上次的半成品。
  (最初直接用 MAX(idx)+1,会让一章失败后序号跳空,改了。)
- 冲突判定:`planned` 缺省按 false(宁可误报重写也不放过);"故意反转"由章纲 `planned_reversals` 声明、入账时核对。
- 入账只返回变化字段时用 `merge_character` 保留旧值,避免 core 等字段被悄悄清零。
- prompts 遵守前身教训:约束放 user 消息末尾;示例只用占位词不放专名。

**未实测**:所有 prompt 的实际效果(模型是否按 JSON 结构输出、核对是否可靠 = 架构风险 #2)。需要密钥后做真实 smoke(已有 Magpie 待办)。
暂不处理:
- 卷满/封卷判断与卷规划(切片 5)。
- 入账与正文是两次独立调用,"摘要+核对"若漏报冲突只能靠后续人工抽查(v0 验收项)。

## 轮 5 — 卷规划 + 封卷

做了:`pipeline/volume.py`(`plan_volume` / `seal_volume` / `ensure_active_volume`)、`volume_prompts.py`、`parsing.py` 增加两个解析器;
抽出 `llm_step.call_step`(调用+记账,章与卷共用)和 `errors.py`(失败类型)。全库 47 个测试全绿(FakeLLM)。

决策:
- 卷满的判据 = 已定稿章数 ≥ `volumes.target_chapters`(规划时由编辑给出,越界 5~200 外回退默认 30)。schema 为此加了一列。
- **封卷原子**:卷摘要 + 刷新全书梗概在同一事务;封卷解析失败则卷仍是 active,下次调度重试(测试覆盖)。
- `ensure_active_volume` 是调度器每次写章前的入口,`generate_chapter` 本身不管卷的生命周期(单一职责)。
- 封卷时未回收的伏笔**不清理**,留在账本里由下一卷规划的"要收的伏笔"接手。

暂不处理:
- `cost_summary` 只统计带章序号的步骤,卷规划/封卷的费用(chapter_idx 为空)没算进"单章平均成本",会略低估;
  v0 验收要成本数字时,在 summary 里补"摊销卷级成本"。
- schema 改了列但没有迁移机制(本地尚无真实数据库,无影响;上 13 前必须决定迁移方案)。

## 轮 6 — 预生成缓冲调度

做了:`scheduler.py`:`top_up`(单本书补货到 `buffer_chapters`)、`top_up_all`(所有连载中的书,互不拖累)。8 个测试,全库 55 个全绿。

决策:
- 只做"补货"一件事;每次生成前先 `ensure_active_volume`,卷的生命周期仍归 volume 模块。
- **失败不重试、要可见**:一章最终失败(`ChapterFailed`/`LLMError`)就停手,把摘要写进新增的 `books.gen_error`,成功后清空——
  界面据此提示"生成遇到问题",杜绝"后台失败但用户以为成功"。重试节奏由外层循环决定(切片 8)。
- 并发:同一本书同时只允许一个补货(进程内 `threading.Lock`,非阻塞获取,拿不到就 `skipped`)。

暂不处理:
- 锁是进程内的;v0 单进程部署够用,上多 worker 要换成库级租约。
- 没有"失败后退避/连续失败暂停"的策略(例如密钥失效时每轮都会打一次 401);外层循环做退避时一并处理。
- `books.gen_error` 是又一次无迁移的 schema 改动,同上"上 13 前定迁移方案"。
