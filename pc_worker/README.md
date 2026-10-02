# 话本配音程序(电脑端)

跑在你的电脑上(RTX 3060),从话本服务器取配音任务,用本地中文 TTS 模型合成 MP3 交回。
电脑主动连服务器(局域网 / Tailscale),**不用开端口**;开着就干活,关掉就停——书页会提醒"请打开电脑上的配音程序"。

## 安装(一次)

```
cd pc_worker
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe torch --index-url https://download.pytorch.org/whl/cu124
uv pip install --python .venv/Scripts/python.exe -r requirements-kokoro.txt
```

## 运行

```
.venv\Scripts\python.exe -m huaben_voice --server http://10.1.1.13:8210 --engine kokoro-zh --voice zf_001
```

- `--voice`:`zf_xxx` 女声、`zm_xxx` 男声(Kokoro-82M-v1.1-zh 自带一百多个)。`--speed` 语速倍率。
- `--token`:服务器设了 `HUABEN_VOICE_WORKER_TOKEN` 时必填。
- 一次只取一章,做完再问下一章;服务器按"谁接下来要听哪章"排好顺序,多本书轮流。
- 出错(服务器重启、网络抖动、单章合成失败)只记一行日志,指数退避后继续,不退出。

## 引擎

| 引擎 | 说明 |
|---|---|
| `kokoro-zh` | Kokoro-82M-v1.1-zh(hexgrad 的中文专用版)。**当前在用** |
| `fake` | 空跑/测试用,不需要 GPU |

实测(2026-10-02,RTX 3060):启动加载约 40 秒(首次另需下载约 330MB 模型);合成约 **26 倍实时**——
1037 字 → 3.6 分钟音频用 8.4 秒,一章 2500 字约 20 秒;MP3 约 6.4KB/秒音频(24kHz)。

表现力更强的 CosyVoice2 / IndexTTS2 留到"使用中优化质量"阶段再比;接口相同(`synthesize(text) -> MP3 bytes`),
在 `huaben_voice/engines.py` 加一项即可。

## 装的时候踩过的坑

- 不钉 `transformers>=4.44` 时,解析器退回 transformers 4.12 → tokenizers 0.10 只有源码包,Windows 上现场编译 Rust 失败。
- misaki 处理中文里夹的英文词要 spaCy 英文模型 `en_core_web_sm`;运行时自动下载在 uv 环境里会失败(uv 环境没有 pip)
  且直接退出,所以写进了 requirements 预装。
- 日志重定向到文件时是 GBK 编码(Windows 控制台代码页);直接在命令行窗口看是正常的。
