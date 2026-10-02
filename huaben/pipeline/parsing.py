"""解析并校验编辑步骤的输出:取 JSON(jsonout)→ 规整成确定形状(normalize)。纯函数。

结构不对则抛 ParseError,由流水线当作一次失败的尝试处理,不会带着残缺数据入账。
"""
from .jsonout import ParseError, extract_json, need  # noqa: F401  (对外统一从这里取)
from .normalize import normalize_ledger, normalize_outline


def parse_outline(text: str) -> dict:
    return normalize_outline(extract_json(text))


def parse_ledger(text: str) -> dict:
    return normalize_ledger(extract_json(text))


def unplanned_contradictions(ledger: dict) -> list[str]:
    """只有非"有意反转"的冲突才算硬伤(ledger 已规整,planned 一定是 bool)。"""
    return [c["what"] for c in ledger["contradictions"] if not c["planned"]]


def parse_volume_plan(text: str) -> dict:
    d = extract_json(text)
    if not need(d, "goal", str).strip():
        raise ParseError("empty goal")
    for k in ("beats", "plant", "resolve"):
        d.setdefault(k, [])
        need(d, k, list)
    if not d["beats"]:
        raise ParseError("volume plan has no beats")
    n = d.get("target_chapters")
    d["target_chapters"] = n if isinstance(n, int) and 5 <= n <= 200 else None  # 越界交给调用方用默认值
    return d


def parse_seal(text: str) -> dict:
    d = extract_json(text)
    for k in ("volume_summary", "synopsis"):
        if not need(d, k, str).strip():
            raise ParseError(f"empty {k}")
    return d
