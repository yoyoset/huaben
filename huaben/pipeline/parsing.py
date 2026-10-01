"""解析并校验编辑步骤的 JSON 输出。纯函数。

模型常把 JSON 包在 ```json 围栏里或前后加话,这里容忍;结构不对则抛 ParseError,
由流水线当作一次失败的尝试处理,不会带着残缺数据入账。
"""
import json
import re


class ParseError(Exception):
    pass


def extract_json(text: str) -> dict:
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, flags=re.S)
    if m:
        t = m.group(1).strip()
    if not t.startswith("{"):  # 前后夹杂说明文字:取第一个 { 到最后一个 }
        a, b = t.find("{"), t.rfind("}")
        if a == -1 or b <= a:
            raise ParseError(f"no JSON object in output: {text[:120]!r}")
        t = t[a:b + 1]
    try:
        data = json.loads(t)
    except ValueError as e:
        raise ParseError(f"invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ParseError("JSON top level is not an object")
    return data


def _need(data: dict, key: str, typ):
    if not isinstance(data.get(key), typ):
        raise ParseError(f"field {key!r} missing or not {typ.__name__}")
    return data[key]


def parse_outline(text: str) -> dict:
    d = extract_json(text)
    if not _need(d, "title", str).strip() or not _need(d, "outline", str).strip():
        raise ParseError("empty title/outline")
    _need(d, "hook", str)
    d.setdefault("characters", [])
    d.setdefault("foreshadows", [])
    d.setdefault("planned_reversals", [])
    for k in ("characters", "foreshadows", "planned_reversals"):
        _need(d, k, list)
    return d


def parse_ledger(text: str) -> dict:
    d = extract_json(text)
    if not _need(d, "summary", str).strip():
        raise ParseError("empty summary")
    for k in ("characters", "foreshadows_new", "foreshadows_update", "facts", "contradictions"):
        d.setdefault(k, [])
        _need(d, k, list)
    for c in d["characters"]:
        if not isinstance(c, dict) or not str(c.get("name", "")).strip():
            raise ParseError("character entry without name")
    return d


def unplanned_contradictions(ledger: dict) -> list[str]:
    """只有非"有意反转"的冲突才算硬伤。planned 缺省按 False 处理(宁可误报也不放过)。"""
    return [str(c.get("what", "")) for c in ledger["contradictions"]
            if isinstance(c, dict) and not c.get("planned", False)]
