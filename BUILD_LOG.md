# 构建日志

按 loop 轮次追加。记录:做了什么 / 踩的坑(含"最初以为 A,实测是 B") / 已知但暂不处理的问题。
范围依据 `docs/v0-scope.md`;不部署到 13、不做对外操作。

## 路线(切片顺序)

1. [x] 脚手架 + 配置 + SQLite schema + repo 层
2. [ ] LLM 客户端(OpenRouter,关思考、惩罚=0、记 token/耗时/费用;可注入 fake 以便测试)
3. [ ] 分层记忆 → prompt 组装(纯函数)
4. [ ] 章节流水线:章纲 → 正文 → 入账+核对(打回重写)
5. [ ] 卷规划 + 封卷
6. [ ] 预生成缓冲调度
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
