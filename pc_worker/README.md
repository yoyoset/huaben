# 话本配音程序(电脑端)

跑在你的电脑上(RTX 3060),从话本服务器取配音任务,用本地中文 TTS 模型合成 MP3 交回。
电脑主动连服务器(局域网 / Tailscale),**不用开端口**;开着就干活,关掉就停——书页会提醒"请打开电脑上的配音程序"。

```
cd pc_worker
python -m huaben_voice --server http://10.1.1.13:8210 --engine fake
```

- `--token`:服务器设了 `HUABEN_VOICE_WORKER_TOKEN` 时必填。
- 一次只取一章,做完再问下一章;服务器按"谁接下来要听哪章"排好顺序,多本书轮流。
- 出错(服务器重启、网络抖动、单章合成失败)只记一行日志,指数退避后继续,不退出。

## 引擎(待定)

目前只有 `fake`(空跑/测试用)。真实的中文模型要**先出样音、你试听后再定**:
候选是能在 3060(12GB)上跑的中文模型,例如 CosyVoice2、IndexTTS2;爱读用的 Kokoro 目前只配了英文。
定下来后在 `huaben_voice/engines.py` 加一个引擎(接口:`synthesize(text) -> MP3 bytes`),
MP3 编码用 `soundfile`(libsndfile ≥ 1.1 可直接写 MP3,2026-10-02 在爱读的环境里实测可用)。
