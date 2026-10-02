"""朗读前的文本处理。纯函数。"""
import re

# 全角标点用 \u 转义写(原因见 pipeline/draft_check.py):句号 叹号 问号 省略号 右引号 右直角引号
_SENTENCE_END = re.compile("(?<=[!?。！？…”」』])")


def clean_for_tts(text: str) -> str:
    """去掉朗读时会被念成怪声的符号(markdown 标记、分隔线),保留标点以保持停顿。"""
    t = re.sub(r"^\s*[-*_=]{3,}\s*$", "", text, flags=re.M)  # 分隔线
    t = re.sub(r"[*_`#>]+", "", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def split_for_tts(text: str, max_chars: int) -> list[str]:
    """按段落切块,每块 ≤ max_chars;单段过长再按句末标点切;句子仍超长则硬切。不丢字、不重复。"""
    chunks: list[str] = []
    cur = ""

    def flush():
        nonlocal cur
        if cur.strip():
            chunks.append(cur.strip())
        cur = ""

    pieces: list[str] = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            pieces.append(para)
            continue
        for sent in _SENTENCE_END.split(para):
            while len(sent) > max_chars:
                pieces.append(sent[:max_chars])
                sent = sent[max_chars:]
            if sent:
                pieces.append(sent)
    for piece in pieces:
        if cur and len(cur) + 1 + len(piece) > max_chars:
            flush()
        cur = f"{cur}\n{piece}" if cur else piece
    flush()
    return chunks
