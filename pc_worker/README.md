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
- **关窗口 = 停止配音**(正在配一章时会先问);**最小化或点「收进托盘」= 后台继续配**,双击托盘图标再打开。
- 只允许开一个(开两个会抢显卡)。启动器被强行结束时,配音进程会跟着结束,不会留在后台偷偷占显卡。
- 引擎、音色(女声/男声)、服务器地址:点「改设置」用记事本改 `HuabenVoice.ini`,再点「重新启动」。

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
| `qwen3-zh` | Qwen3-TTS 1.7B + faster-qwen3-tts,**克隆 `voices/` 里的参考音**(女声 / 男声)。**当前在用**,装在 `.venv-qwen` |
| `kokoro-zh` | Kokoro-82M-v1.1-zh。快(26 倍实时)但音色一般;装在 `.venv` |
| `fake` | 空跑/测试用,不需要 GPU |

**qwen3-zh 安装**:见 `requirements-qwen.txt` 文件头(先装 CUDA 版 torch 2.11+cu128,再用 `torch-pin.txt` 约束装其余)。
模型首次运行从 HuggingFace 下载(Base 约 4.5GB)。

**音色**:`voices/<名字>.wav` 是一段约 10 秒的参考音,`<名字>.txt` 是参考音里说的话;设置里写 `voice=<名字>`。
整本书每一段都克隆同一段参考音,所以前后一致。换音色后,服务器会把读者**还没听到**的章用新音色重配(听过的不动)。

实测(2026-10-03,RTX 3060 12GB,Windows):
- 速度:约 2 倍实时,峰值显存约 5GB;一章 1776 字约 3 分钟。
- 为什么用克隆而不是内置音色/一句话描述音色:后两者每段都是现场生成的声音,段与段之间漂——同一段 4 段正文的每段音高中位数,
  Serena 内置 241/269/204/251 Hz,描述出来的评书男声 87/260/157/180 Hz(像换了人);克隆后 女 236~277、男 174~208。
- 为什么用 faster-qwen3-tts:官方 qwen-tts 在 Windows 上只有 0.12 倍实时(每步约 500 次小 kernel 启动,开销压倒计算)。
- 防失控:一段偶尔会"停不下来"一直生成到上限(实测 200 字生成了 161 秒);现在上限按字数给,超长就重来。

接口相同(`synthesize(text) -> MP3 bytes`),换引擎在 `huaben_voice/engines.py` 加一项即可。

## 装的时候踩过的坑

- 不钉 `transformers>=4.44` 时,解析器退回 transformers 4.12 → tokenizers 0.10 只有源码包,Windows 上现场编译 Rust 失败。
- misaki 处理中文里夹的英文词要 spaCy 英文模型 `en_core_web_sm`;运行时自动下载在 uv 环境里会失败(uv 环境没有 pip)
  且直接退出,所以写进了 requirements 预装。
- 日志重定向到文件时是 GBK 编码(Windows 控制台代码页);启动器设了 `PYTHONIOENCODING=utf-8`,还要 `PYTHONUNBUFFERED=1`,
  否则管道里的输出整块缓冲,窗口要很久才出字。
- uv 建的 venv 里 `python.exe` 是个转发器,会再起一个真正的 python 子进程;启动器用"关闭即结束"的作业对象兜住两层。
- `.cmd` 文件必须是 CRLF 换行,LF 换行时 cmd.exe 会把行拆碎乱执行(第一次编译就踩了)。
- qwen-tts 不钉 torch,`-U` 安装时把 CUDA 版 torch 换成了 PyPI 上的 CPU 版(`torch.cuda.is_available()` 为 False),所以要用 `torch-pin.txt` 约束。
- faster-qwen3-tts 要 transformers 5.15.x:5.18 报 `MimiConfig` 没有 `rope_theta`;4.57 报 `StaticLayer.lazy_initialization` 参数个数不对。
- 两个引擎的 transformers 大版本冲突(5.x vs 4.x),所以各用一个虚拟环境;系统里的 CUDA 工具包用不上——pip 装的 torch 自带运行库,只依赖显卡驱动。
