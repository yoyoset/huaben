# T001 配音:跨段落合并,不再几秒几秒地生成

## 为什么

2026-10-03 用户:配音是几秒几秒生成的,个别语句的声音和前后对不上;为什么不一次生成整章?

架构方实测(生产《算尽仙朝》第 13 章,3972 字,本地样本 `samples/voice_bench/chapter.txt`):
现在的切法把这一章切成 **133 段,其中 43 段不到 10 字、95 段不到 30 字、112 段不到 60 字**。
当天的配音日志 1698 次生成里 14% 不到 2 秒、40% 不到 6 秒。

原因:`kokoro_zh.segments()` **先按段落切、段内才拼句**,从不跨段落合并。小说里一句对白就是一个段落,
于是每句对白单独生成一次。克隆音色在很短的文本上最不稳(没有上下文,音高、语速、语气每次重新"想"),
这就是"个别语句错位"。

**为什么不是整章一次生成**(已定,不要改):这个模型一次生成的默认上限是 2048 个 token ≈ 170 秒,一章约 800 秒;
而且 `qwen3_zh.py` 里记录过不到 200 字的一段都会"停不下来"生成 161 秒乱音——一次生成越长,失控和漂移的概率越高,
失控一次要重来的代价也越大。所以方案是:**在稳定的前提下每块尽量长**,而不是整章一块。
具体多长最好,由 T002 在显卡上实测后架构方再定;本卡先做到"约 200 字一块、没有碎块"。

## 已定的方案

新建 `pc_worker/huaben_voice/chunks.py`,只放下面这个纯函数(参考实现已在真实章节上验证:133 段 → 21 块,
最短 135 字,不丢字)。照抄,不要改算法:

```python
"""朗读前把一章切成块:跨段落合并到约 target 字一块。纯函数。(文件头注释写清"为什么",内容见任务卡 T001 的"为什么"一节)"""
from .kokoro_zh import segments


def chunks(text: str, target: int = 200, ceiling: int = 300, floor: int = 60) -> list[str]:
    units = [s for para in segments(text, target) for s in para]
    out, cur = [], ""
    for u in units:
        if cur and len(cur) + len(u) > target:
            out.append(cur)
            cur = ""
        cur += u
    if cur:
        out.append(cur)
    i = 0
    while i < len(out) and len(out) > 1:
        j = i - 1 if i > 0 else i + 1          # 优先并进前一块;第一块只能并进后一块
        if len(out[i]) < floor and len(out[i]) + len(out[j]) <= ceiling:
            lo, hi = min(i, j), max(i, j)
            out[lo:hi + 1] = [out[lo] + out[hi]]
            i = lo
        else:
            i += 1
    return out
```

文件头的 docstring 要自己写完整:把上面"为什么"里的实测数字(133 段/43/95/112、14%/40%)和"为什么不是整章一次"写进去。

## 改哪些文件

1. **新建** `pc_worker/huaben_voice/chunks.py`:如上。
2. **改** `pc_worker/huaben_voice/qwen3_zh.py`:
   - `synthesize()` 改成按 `chunks(text, MAX_SEG_CHARS)` 逐块生成;每块之后加一段静音。
   - 常量 `PARAGRAPH_PAUSE_S = 0.5` 改名为 `CHUNK_PAUSE_S = 0.35`(块与块之间;块内的停顿由模型按标点自己处理)。
   - `MAX_SEG_CHARS = 200` 保留不动,它旁边的注释补一句"块长的实测见 T002"。
   - `from .kokoro_zh import encode_mp3, segments` 里不再用到的名字去掉。
   - 文件头 docstring 里"一章要切成几十段分别合成"那一段后面补一句:2026-10-03 改为跨段落合并,见 `chunks.py`。
   - 其它(`token_cap`、`runaway`、`_say`、重试)**不要动**。
3. **不要动** `kokoro_zh.py`(它的 120 字上限是模型音素上限,而且它是备用引擎)。
4. **新建** `tests/test_voice_chunks.py`(导入方式照抄 `tests/test_pc_worker.py` 开头的 `sys.path.insert`):
   - `test_no_char_lost`:对一段含多段落、对白、长句的文本,`"".join(chunks(t)) == "".join(p.strip() for p in t.split("\n"))`。
   - `test_dialogue_lines_are_merged`:20 个各 8 字的对白段落(每段以 `”` 结尾) → 结果只有 1 块。
   - `test_every_chunk_within_ceiling`:任意输入每块 `len <= ceiling`。
   - `test_no_tiny_chunk_when_mergeable`:3000 字左右、长短段落混排的文本,没有任何一块 `< floor`。
   - `test_single_short_text`:只有 5 个字 → 返回 1 块,就是这 5 个字。
   - `test_empty_text`:空串和只有空行 → 返回 `[]`。
   测试文本自己在测试里造(用 `"他说了一句话。" * n` 这类),不要读 `samples/`(那个目录不进 git)。

## 验收标准

1. `python -m pytest -q` 全过(开工前是 383 项,做完应是 389 项)。
2. 下面这条命令的输出贴进报告,应为 `133 -> 21`(块数允许 ±1),且 `min >= 60`:
   ```bash
   python -c "import sys; sys.path.insert(0,'pc_worker'); from huaben_voice.kokoro_zh import segments; from huaben_voice.chunks import chunks; t=open('samples/voice_bench/chapter.txt',encoding='utf-8').read(); a=[s for p in segments(t,200) for s in p]; b=chunks(t); print(len(a),'->',len(b),'min',min(map(len,b)),'max',max(map(len,b)))"
   ```
3. `tests/test_structure.py` 通过(单文件 ≤ 200 行)。

## 这次不做

- 不动显卡、不实际合成音频(那是 T002)。
- 不改块长 200(等 T002 的数字)。
- 不给已经配好的旧章重配(换切法后要不要重配由用户定)。
- 段落末尾没有标点时不补标点(小说正文极少见;补了会破坏"不丢字不加字")。

## 审核记录

**通过(2026-10-03)**。架构方重跑:401 项测试全过;真实章节 133 段 → 21 块(最短 135、最长 198 字);`qwen3_zh.py` 改动与卡一致(局部变量改名 `pieces` 是合理偏差)。未在显卡上合成,留给 T002。
电脑上的『话本配音』重启后才用上新切法。
