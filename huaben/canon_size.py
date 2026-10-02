"""世界设定定本的长度观测。

为什么要看:定本每次封卷由模型把"旧定本 + 本卷事实"合并压缩,不截断(截断会悄悄丢掉最早、最根本的设定),
而且每一章的生成都整段带上它。模型合并得不好(只加不删)时,定本会卷卷变长:单章成本上升、
真正要紧的设定被稀释——这一切此前没有任何观测,只能等读者发现"越写越贵 / 越写越乱"。

阈值的依据:默认单章正文 2500 字;定本超过 4000 字(比一章正文还长得多)时,它已是 prompt 里最大的块之一,
值得人看一眼(是故事本身设定多,还是合并没去重)。这是观测线,不是截断线——超了只告警,不动内容。
"""
CANON_WARN_CHARS = 4000


def canon_size(canon: str | None) -> dict:
    text = (canon or "").strip()
    return {
        "chars": len(text),
        "lines": sum(1 for line in text.splitlines() if line.strip()),
        "warn_chars": CANON_WARN_CHARS,
        "too_long": len(text) > CANON_WARN_CHARS,
    }


def seal_note(old: str | None, new: str | None) -> str:
    """封卷留痕用:定本前后字数,便于从运行记录里看出它是否卷卷只增不减。"""
    before, after = canon_size(old), canon_size(new)
    warn = f"(超过 {CANON_WARN_CHARS} 字,建议检查是否没去重)" if after["too_long"] else ""
    return f"定本 {before['chars']}→{after['chars']} 字{warn}"
