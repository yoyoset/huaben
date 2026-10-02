"""解析并校验编辑步骤的输出:取 JSON(jsonout)→ 规整成确定形状(normalize)。纯函数。

结构不对则抛 ParseError,由流水线当作一次失败的尝试处理,不会带着残缺数据入账。
"""
import re

from .jsonout import ParseError, extract_json, need  # noqa: F401  (对外统一从这里取)
from .normalize import normalize_ledger, normalize_outline, to_text_list


def parse_outline(text: str) -> dict:
    return normalize_outline(extract_json(text))


def parse_ledger(text: str) -> dict:
    return normalize_ledger(extract_json(text))


def unplanned_contradictions(ledger: dict) -> list[str]:
    """只有非"有意反转"的冲突才算硬伤(ledger 已规整,planned 一定是 bool)。"""
    return [c["what"] for c in ledger["contradictions"] if not c["planned"]]


def _foreshadow_ref(x) -> int:
    """卷计划里"要收的伏笔"必须是账本编号;容忍 "#3"、"#3 玉佩发烫" 这类写法。"""
    if isinstance(x, int) and not isinstance(x, bool):
        return x
    m = re.match(r"\s*#?(\d+)", str(x))
    if not m:
        raise ParseError(f"resolve 需要伏笔编号,得到 {x!r}")
    return int(m.group(1))


def parse_volume_plan(text: str) -> dict:
    d = extract_json(text)
    if not need(d, "goal", str).strip():
        raise ParseError("empty goal")
    d["beats"] = to_text_list(d.get("beats"), "beats")
    d["plant"] = to_text_list(d.get("plant"), "plant")
    resolve = d.get("resolve") or []
    if not isinstance(resolve, list):
        raise ParseError("resolve 不是列表")
    d["resolve"] = list(dict.fromkeys(_foreshadow_ref(x) for x in resolve))
    if not d["beats"]:
        raise ParseError("volume plan has no beats")
    n = d.get("target_chapters")
    d["target_chapters"] = n if isinstance(n, int) and 5 <= n <= 200 else None  # 越界交给调用方用默认值
    return d


def parse_seal(text: str, canon_required: bool = False) -> dict:
    """canon_required:旧定本或本卷事实非空时,新定本不能为空——否则封卷后这些事实会从 prompt 里消失。"""
    d = extract_json(text)
    for k in ("volume_summary", "synopsis"):
        if not need(d, k, str).strip():
            raise ParseError(f"empty {k}")
    canon = d.get("canon")
    if isinstance(canon, list):  # 模型常把"每行一条"给成数组
        canon = "\n".join(str(x).strip() for x in canon if str(x).strip())
    if canon is not None and not isinstance(canon, str):
        raise ParseError("canon 不是文本")
    d["canon"] = (canon or "").strip()
    if canon_required and not d["canon"]:
        raise ParseError("canon 为空,会丢失已确立的世界事实")
    return d
