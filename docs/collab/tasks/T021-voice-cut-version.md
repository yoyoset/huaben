# T021 配音:切法变了,要让服务器知道(旧切法配的章自动重配)

依赖:无。只动 `pc_worker/huaben_voice/` 和一个测试文件,不动服务器代码。

## 为什么

2026-10-03 用户:"我看了一下分块还是很细碎。"实测原因:T001(跨段落合并成约 200 字一块)是 14:47 提交的,
而电脑上的配音程序是当天 00:52 启动的,一直没重启,跑的还是旧代码——日志里第 2 章(3406 字)生成了 95 次,
最短的一段只有 0.58 秒;同一章用现在的 `chunks()` 切是 18 块。所以**重启配音程序就好了**。

剩下两个问题,这张卡解决:

1. 旧切法配出来的章(生产上第 1、2 章)不会自动重配:服务器只在"音色标签变了"时才把读者还没听的章排进重配队列
   (`huaben/tts/service.py` 的 `stale_voice`),而换切法没有改变标签。
2. 从窗口里看不出跑的是新代码还是旧代码。

## 已定的方案

### 1. `pc_worker/huaben_voice/chunks.py`

在 `from .kokoro_zh import segments` 之后、`def chunks` 之前加一个常量:

```python
CUT_VERSION = "c200"  # 切法的版本:改了切块办法或默认块长,就改它——服务器据此把旧切法配的、读者还没听的章重配
```

### 2. `pc_worker/huaben_voice/__main__.py`

- `voice_id` 改成:引擎是 `qwen3-zh` 时,在标签末尾加 `:` 和 `CUT_VERSION`;别的引擎不变。

  ```python
  def voice_id(engine: str, voice: str, instruct: str = "") -> str:
      tag = f":{hashlib.sha1(instruct.encode()).hexdigest()[:6]}" if instruct else ""
      cut = f":{CUT_VERSION}" if engine == "qwen3-zh" else ""
      return f"{engine}:{voice}{tag}{cut}"[:120]
  ```

  函数的说明文字里补一句"qwen3-zh 的切法版本变了也算"。`CUT_VERSION` 从 `.chunks` 导入。
- `main()` 里,在 `log.info("引擎就绪,开始向 %s 取配音任务", args.server)` **之前**加一行:

  ```python
  log.info("音色标签 %s", voice_id(args.engine, args.voice, args.instruct))
  ```

### 3. 测试(加在 `tests/test_pc_worker.py`)

```python
def test_voice_id_carries_the_cut_version_for_qwen():
    from huaben_voice.__main__ import voice_id
    from huaben_voice.chunks import CUT_VERSION
    assert voice_id("qwen3-zh", "女声") == f"qwen3-zh:女声:{CUT_VERSION}"
    assert voice_id("kokoro-zh", "zf_001") == "kokoro-zh:zf_001"
    assert voice_id("qwen3-zh", "女声", "慢一点").endswith(f":{CUT_VERSION}")
    assert voice_id("qwen3-zh", "女声", "慢一点") != voice_id("qwen3-zh", "女声")
```

导入 `huaben_voice.__main__` 不会启动程序(它只在 `__name__ == "__main__"` 时调用 `main()`);导入失败就停,状态改「卡住」。

### 4. `pc_worker/README.md`

在"运行"一节末尾加一条:

`- 改了配音程序的代码(包括切块办法)之后要点「重新启动」才生效;启动后日志里有一行"音色标签 qwen3-zh:女声:c200",末尾的 c200 是切法版本。`

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化(现在 496)。
2. `tests/test_structure.py` 通过。
3. 报告贴出这条命令的真实输出:

   ```
   python -c "import sys;sys.path.insert(0,'pc_worker');from huaben_voice.__main__ import voice_id;print(voice_id('qwen3-zh','女声'))"
   ```

## 这次不做

- 不改块长(仍是 200;T002 实测 200 与 400 一致性相同)。
- 不改服务器、不重启配音程序、不碰显卡。

## 审核记录

通过 2026-10-03。这张卡同时让四个模型各做了一遍(各自的工作副本,互不干扰),四份代码改动一字不差,497 项全过;采用 deepseek-v4.1-flash 的那一份。
架构方重跑:`python -m pytest -q` 497 全过。用时:muse-spark-1.3 148 秒、deepseek-v4.1-flash 160 秒、glm-5.3-flash 175 秒、mimo-v2.6-flash 500 秒。
差别只在报告和看板:mimo 多改了看板的"当前"一行(那一行归架构方,它在偏差里如实写了);deepseek 和 glm 都注意到命令输出的乱码并说明了原因。
这张卡太小、方案写得太死,分不出模型高下;T020 再比一次。
