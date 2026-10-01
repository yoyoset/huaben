# 话本 Huaben

AI 私人连载 + 听书。开一本书只需要一次对话,之后一键往下看、或者锁屏听。

> 宋代"话本"是写给说书人拿去讲的故事底本——既能读,也能听。这个工具做的是同一件事。

## 一句话定位

**给一个读者的私人无限连载。**用户是读者,不是合著者:意图只在"开书"时输入(类型、喜欢的样章、雷点、爽点密度),
之后系统自己掌舵,一章接一章往下写;想换口味就开一本新书。

## 要解决的两个核心问题

1. **长篇续写的遗忘**——名字漂移、伏笔断线、文风漂移、方向漂移。
   解法不是更大的上下文,而是模仿真人连载作者:卷纲、人物卡、伏笔账本,由程序维护,每章读写。
2. **读起来有人味**——能看、能听;锁屏能播、自动下一章、睡眠定时;旁白与角色分声音、有情绪。

## 文档

- [docs/architecture.md](docs/architecture.md) — 架构与关键决策(含"为什么")
- [docs/v0-scope.md](docs/v0-scope.md) — 第一版做什么、不做什么
- [docs/lessons-from-sillytavern.md](docs/lessons-from-sillytavern.md) — 前身(酒馆小说连载模式)实测踩过的坑
- [assets/logo.svg](assets/logo.svg) — logo 草稿:醒木 + 油灯("灯下说书")

## 本地跑起来

```bash
pip install -r requirements-dev.txt
cp .env.example .env        # 填 HUABEN_OPENROUTER_API_KEY
python -m pytest -q         # 全部测试(不碰网络)
python -m huaben            # http://127.0.0.1:8000 ,手机宽度打开最像成品
```

部署到 13 见 [docs/deploy.md](docs/deploy.md);开发进度与踩坑日志见 [BUILD_LOG.md](BUILD_LOG.md)。

## 来历

2026-09 在家用 SillyTavern(10.1.1.13:8100)上给家人搭了"小说连载模式":点「下一章」连载、打字提意见、Edge 晓晓朗读。
验证了需求是真的(剧情好看,但"不想玩、想看/想听"),也撞到了酒馆作为聊天工具的天花板——
遗忘只能靠摘要硬扛、没有规划层、锁屏不能听。于是另起炉灶。
