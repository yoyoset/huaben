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

## 运行:双击 `HuabenVoice.exe`

`pc_worker\HuabenVoice.exe`(桌面上也有快捷方式「话本配音」)。打开后是一个窗口 + 右下角托盘里的话本图标(灯):

- 窗口顶上一行是当前状态:正在加载模型 / 等待任务 / 正在配第几章 / 出错自动重试 / 已停止;下面是完整日志,
  同时存到 `pc_worker/logs/voice-日期.log`。
- **关窗口 = 停止配音**(正在配一章时会先问);**最小化或点「收到托盘」= 后台继续配**,双击托盘图标再打开。
- 只允许开一个(开两个会抢显卡)。启动器被强行结束时,配音进程会跟着结束,不会留在后台偷偷占显卡。
- 音色、语速、服务器地址:点「改设置」用记事本改 `HuabenVoice.ini`,再点「重新启动」。

启动器源码在 `launcher/`,用 Windows 自带的 .NET Framework 编译器编译,不用装任何东西:
双击 `launcher/build.cmd` 生成 `HuabenVoice.exe`(exe 与 ini 不进 git)。

命令行方式(调试用):

```
.venv\Scripts\python.exe -m huaben_voice --server http://10.1.1.13:8210 --engine kokoro-zh --voice zf_001
```

- `--voice`:`zf_` 开头女声、`zm_` 开头男声,编号不连续(2026-10-02 从模型仓库列出,共 103 个,含 3 个英文音色):
  女声 zf_001~008、017~019、021~024、026~028、032、036、038~040、042~044、046~049、051、059、060、067、070~079、083~088、090、092~094、099;
  男声 zm_009~016、020、025、029~031、033~035、037、041、045、050、052~058、061~066、068、069、080~082、089、091、095~098、100。
  `--speed` 语速倍率。
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
- 日志重定向到文件时是 GBK 编码(Windows 控制台代码页);启动器设了 `PYTHONIOENCODING=utf-8`,还要 `PYTHONUNBUFFERED=1`,
  否则管道里的输出整块缓冲,窗口要很久才出字。
- uv 建的 venv 里 `python.exe` 是个转发器,会再起一个真正的 python 子进程;启动器用"关闭即结束"的作业对象兜住两层。
- `.cmd` 文件必须是 CRLF 换行,LF 换行时 cmd.exe 会把行拆碎乱执行(第一次编译就踩了)。
