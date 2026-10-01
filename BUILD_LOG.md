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
7. [x] 保底 TTS(edge-tts → MP3;真实合成待实测)
8a. [x] 开书对话服务(opening/)
8b. [x] FastAPI 路由(书架/章节/播放/进度/开书/状态)
8c. [x] 后台常驻循环(重启恢复 + 失败退避)+ 启动入口
9. [x] PWA 前端(书架/阅读/播放器/Media Session/睡眠定时)
10. [x] Dockerfile + docker-compose + 备份脚本(仅文件,不部署)
11. [ ] 数据库迁移机制(上线前硬前置)
12. [ ] 端到端模拟:FakeLLM 连载 35 章跨卷,核对记忆/账本/卷封存不变量

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

## 轮 7 — 保底 TTS

做了:`tts/` 包:`base.py`(窄接口 `TTS.synthesize(text)->bytes`)、`text.py`(清洗 + 按段落/句末切块,不丢字)、`mp3.py`(`is_mp3` 校验)、
`edge.py`(edge-tts 真实现,惰性导入)、`service.py`(切块→逐块合成+重试→拼接→原子落盘→登记)、`fake.py`;`repo/audio.py`;
调度器 `top_up(..., tts=)` 在补文本之后顺带给缺音频的章配音。全库 67 个测试全绿。

决策:
- **格式把关在入库前**:每块合成结果必须过 `is_mp3`,否则显式失败且不重试(前身教训:插件默认吐 WebM/Opus)。
- 分块合成后字节直接拼接(MP3 是帧流);文件先写 `.tmp` 再 `os.replace`,播放器看不到半成品。
- 朗读开头报"第N章,标题。"。
- 配音失败**不阻断文本缓冲**,但写进 `books.gen_error`("第N章配音失败…"),与文本失败同一个可见通道。
- 删掉了 `Settings.tts_format`:edge-tts 库并不暴露输出格式参数,留着这个配置项等于撒谎。

**未实测(最初的假设,待核对)**:本机没装 edge-tts,`EdgeTTS` 只写没跑。假设"库默认输出 24kHz/48kbps 单声道 MP3"是凭记忆,
没有拿运行结果核对过;`is_mp3` 只验证"是 MP3",不验证码率。已记 Magpie 待办:装库后真实合成一段,查文件头与时长。
暂不处理:
- 没有读取 MP3 时长(`audio.duration_s` 恒为空);播放器进度条用 `<audio>` 自己的 duration 即可,真需要再加。
- 单块 1500 字是拍的数,edge-tts 单次请求的真实上限没测。

## 轮 8a — 开书对话

做了:`opening/` 包:`prompts.py`(向导 + 定稿指令)、`parsing.py`、`service.py`(`opening_turn` 逐轮对话、`finalize_book` 定稿并启动第 1 卷);
表 `opening_messages` + `repo/opening.py`。全库 76 个测试全绿(FakeLLM)。路由层留给 8b,本轮只做服务。

决策:
- **样章不让 LLM 转述**:读者一条消息 ≥200 字就当作粘贴的样章,确定性地原文入库(≤3 段、每段≤1500 字)。
  理由:风格模仿是最大风险(架构风险 #1),转述会把文风洗掉;LLM 只负责写"风格指纹"描述。
- **定稿"缺什么补什么"**:圣经已存在则跳过抽取,卷规划失败重试时不重复花钱;`status` 最后一步才置为 serializing,不留"半开"的书。
- 向导不守 JSON 约定、直接说人话时,把原文当 reply(ready=False),对话不卡死;定稿则严格解析、两次失败显式报错。
- 圣经 + 书信息 + 账本人物同一事务;账本只播种名字与 core 标记,人物定位留在圣经(没把 role 硬塞进 relations)。

暂不处理:
- "ready" 只是向导的建议,读者随时可以手动点"开书"(8b 的接口不依赖它)。
- 对话轮数/长度没有上限保护,真实使用中若 transcript 过长再截断。
- 样章 ≥200 字是拍的阈值。

## 轮 8b — FastAPI 路由

做了:`api/` 包:`app.py`(工厂,设置/LLM/TTS 可注入)、`deps.py`、`background.py`、`routes_books.py`(书架/详情/统计)、
`routes_opening.py`(对话/定稿)、`routes_reading.py`(章节列表/正文/音频/进度)。10 个 TestClient 测试,全库 86 个全绿。

接口:`GET/POST /api/books`、`GET /api/books/{id}`、`/stats`、`GET/POST /opening`、`POST /finalize`、
`GET /chapters`、`GET /chapters/{n}`、`GET /chapters/{n}/audio`、`PUT /progress`、`GET /api/health`。

决策:
- 路由只做"解析→调服务→映射错误":OpeningError→400,LLM/ChapterFailed→502(文案带"可以重试"),没配密钥→503(不是 500)。
- 触发补货的两个时机:开书成功、读者推进 `read_pos`;都用 `BackgroundTasks`,后台任务**自己开连接**(请求级连接此时可能已关)。
- 音频用 `FileResponse`:自带 Range 支持,测试验证了 `Range: bytes=0-3` → 206(iOS `<audio>` 分段取流的前提)。
- 只暴露已定稿的章;章纲不外露(测试断言响应里没有 outline)。
- `PUT /progress` 不允许超过已写好的最后一章。
- 每请求一条连接 + `check_same_thread=False`(同步依赖与端点可能落在不同线程,该连接只服务当前请求)。

暂不处理:
- 没有鉴权(家用 + Tailscale,与 v0 范围一致)。
- 后台补货靠"开书/翻页"触发;服务重启后缓冲不够的书不会自动续补 —— 8c 的常驻循环解决。
- 同一本书两个并发 `POST /opening` 会交错写入对话记录(单读者场景,先不加锁)。
- 真机 iOS 的 Range/锁屏行为仍未验证,只在 TestClient 层面验证了协议。

## 轮 8c — 后台常驻循环 + 启动入口

做了:`worker.py`(`Backoff` 指数退避、`Worker.tick` 单次巡检、守护线程 start/stop)、`api/app.py` 用 lifespan 启停 worker、
`__main__.py`(`python -m huaben`)、配置项 host/port/worker_*/backoff_*。6 个测试,全库 92 个全绿。

决策:
- 常驻循环与"开书/翻页触发的补货"互补:触发式响应快,常驻式负责重启恢复与漏触发。线程**先巡检再等待**,所以服务一启动就补齐。
- 退避按"书"计:失败(文本或配音)指数退避 60s→120s→…封顶 1800s,成功复位;密钥失效时不会每分钟白打一次 401。
- 任何异常只记日志、绝不让线程死掉;单本书的意外不影响其它书。没配密钥时 worker 只打一条 warning 并跳过。
- `Backoff` 时钟可注入,退避逻辑用假时钟测,不 sleep。

**实测**:真起了 `python -m huaben`(127.0.0.1):`/api/health`=200;没配密钥时 worker 打 warning、`POST /opening`=503;
`POST /api/books` 用 httpx 发中文标题=201。
最初以为 `POST /api/books` 返回 400 是应用 bug —— 实测发现是 Windows git-bash 下 `curl -d` 发出的中文不是 UTF-8,
换 httpx 发 UTF-8 即正常。以后命令行烟测中文请求体用 httpx/脚本,不用 curl。

暂不处理:
- 退避状态在内存里,进程重启即清零(重启后立即重试一次,可接受)。
- worker 与 API 触发的补货靠书级进程内锁互斥(同一进程内),符合 v0 单进程部署。

## 轮 9 — PWA 前端

做了:`web/`(无构建步骤的原生 ES 模块):`index.html`(常驻播放条 + 单个复用的 `<audio>`)、`css/app.css`(取自 logo 的墨色/琥珀,浅色模式跟随系统)、
`js/`:`dom.js`(`h`/`fill`,文本一律 textContent)、`api.js`、`logic.js`(纯函数)、`player.js`(单例播放器 + Media Session + 睡眠定时 + 自动下一章 + 等下一章)、
`views/shelf|opening|reader.js`、`main.js`(hash 路由 + SW 注册)、`sw.js`(只缓存应用壳,不缓存 /api 与音频)、`manifest.webmanifest`、图标(由 `assets/logo-preview.png` 缩放,原图未动)。
FastAPI 把 `web/` 挂在 `/`(最后挂载,不盖住 /api)。全库 96 个测试全绿(含 node 跑前端纯逻辑 6 个,不装 node 则跳过)。结构守卫扩展到前端文件(≤200 行)。

**真实浏览器验证**(种子库 + 静音 MP3 帧,本地起 `python -m huaben`,移动视口 375×812):
- 书架:卡片、状态 chip、`gen_error` 红色提示条正常显示;
- 阅读页:文字、上/下章、目录正常;点"听这一章":`<audio>` 经 Range 端点加载,时长 5.2s、currentTime 前进,Media Session 标题=「第1章 夜巡」;
- **自动下一章实测通过**:第 1 章播完后 `audio.src` 自动变为第 2 章、标题/Media Session 同步;最后一章播完进入"下一章还在准备,好了自动接着播…";
- 进度上报:播到第 2 章后 `read_pos=2`;语速循环 1.0→1.25;睡眠定时 关→15→30→60→本章结束→关 循环正确。

踩坑/修正(最初以为 A,实测是 B):
- 最初书架直接 `replaceChildren(..., books.map(card))`,**实测**书卡被渲染成一串 URL 文本;原因是原生 `replaceChildren/append` 不展开数组、会把 `null` 变成文字 "null"。
  修正:`dom.js` 增 `fill()`(展开嵌套数组、跳过 null/false),所有视图改用它,不直接调 replaceChildren。
- Service Worker 在 Claude 内置浏览器里注册失败("fetching the script" 未知错误),但 `/sw.js` 本身 200、MIME 正确 —— 判断是该内置浏览器不支持 SW,**不是代码问题,但尚未在真 Chrome/Safari 验证**。

**仍未验证(需要真机)**:iOS Safari/PWA 的锁屏续播、后台自动下一章(架构风险 #4)——本轮只证明了"复用同一个 audio 元素换 src"在桌面浏览器里行得通;
SW 安装与"添加到主屏幕"体验;iOS 对 Range 的实际表现。

暂不处理:
- 没有"设置"页(默认音色/语速持久化):语速/睡眠定时只在当前会话有效。
- 目录里没有标"已读"。
- 浅色/深色之外没有字号调节。

## 轮 10 — 部署文件 + 备份

做了:`Dockerfile`、`docker-compose.yml`、`.dockerignore`、`.gitattributes`(sh/py 强制 LF)、`scripts/backup.sh`、`huaben/backup.py`(SQLite 在线备份 + 完整性校验 + 轮转)、
`docs/deploy.md`、README 本地运行说明;依赖拆成 `requirements.txt`(运行时)与 `requirements-dev.txt`。全库 106 个测试全绿。

决策:
- **只备份数据库不备份音频**:音频可由正文重新合成,体积大且无不可替代性;恢复后后台自动补配音。
- 备份走 `Connection.backup`(库是 WAL 模式,直接 cp 主文件会丢 WAL 里的新数据 —— 有测试用"另一条写连接未关闭"复现并验证)。
- 容器以 root 运行(避免 bind mount 属主不匹配首次写不进 `/data`;没有 docker 的开发机上无法提前验证这类问题),已写入 deploy.md 的取舍。
- 宿主机端口默认 8210 且需在 13 上确认空闲(8100 是 SillyTavern);备份目录用 `HUABEN_BACKUP_DIR` 可配。

踩坑:
- 测试抓到真缺陷:源库损坏时 `Connection.backup` 抛异常,`dest` 文件(由 `sqlite3.connect` 创建)残留成"看似备份的空壳"。
  修正:任何 sqlite 错误都清理 dest 并统一抛 `BackupError`。

**未验证**:本机没有 docker,Dockerfile/compose **没有真正构建或运行过**,只做了静态自检(`tests/test_deploy_files.py`:密钥不进 compose、
COPY 路径存在、端口对应、测试依赖不进镜像、sh 脚本为 LF);也**没有登录 13 核对 vpsmon/opencode-usage 的实际惯例**(CLAUDE.md 里是转述)。
首次部署后把真实情况回写 `docs/deploy.md` 末尾。恢复演练尚未做。

暂不处理:
- 上线前硬前置:**数据库迁移机制**(下一切片做)。
- 备份不加密、不异地(同在 13 的 /mnt/4t);家用场景先这样。
