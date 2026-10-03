"""朗读前把一章切成块:跨段落合并到约 target 字一块。纯函数。

为什么(2026-10-03 用户:配音几秒几秒地生成,个别语句声音和前后对不上):
旧的 `kokoro_zh.segments()` 先按段落切、段内才拼句,从不跨段落合并;小说里一句对白就是一个段落,
于是一句对白单独生成一次。生产《算尽仙朝》第 13 章(3972 字)实测被切成 133 段,其中 43 段不到 10 字、
95 段不到 30 字、112 段不到 60 字;当天配音日志 1698 次生成里 14% 不到 2 秒、40% 不到 6 秒。
克隆音色在很短的文本上最不稳(没有上下文,音高、语速、语气每次重新"想"),这就是"个别语句错位"。

为什么不是整章一次生成(已定,不要改):这个模型一次生成的默认上限是 2048 个 token ≈ 170 秒,
一章约 800 秒;而且 `qwen3_zh.py` 里记录过不到 200 字的一段都会"停不下来"生成 161 秒乱音——
一次生成越长,失控和漂移的概率越高,失控一次要重来的代价也越大。所以在稳定的前提下每块尽量长,
而不是整章一块。具体多长最好由 T002 在显卡上实测后架构方再定;本卡先做到"约 200 字一块、没有碎块"。
"""
from .kokoro_zh import segments

CUT_VERSION = "c200"  # 切法的版本:改了切块办法或默认块长,就改它——服务器据此把旧切法配的、读者还没听的章重配


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
