"""开书两步的 LLM 输出解析。纯函数。"""
from ..pipeline.parsing import ParseError, extract_json, need


def parse_guide(text: str) -> dict:
    """向导回复。模型偶尔不守 JSON 约定、直接说人话:此时把原文当作 reply,ready=False,不让对话卡死。"""
    try:
        d = extract_json(text)
        if not need(d, "reply", str).strip():
            raise ParseError("empty reply")
        d["ready"] = d.get("ready") is True
        return d
    except ParseError:
        if not text.strip():
            raise
        return {"reply": text.strip(), "ready": False}


def parse_bible(text: str) -> dict:
    d = extract_json(text)
    for k in ("title", "synopsis", "world", "style_fingerprint"):
        if not need(d, k, str).strip():
            raise ParseError(f"empty {k}")
    d.setdefault("genre", "")
    d.setdefault("taboos", [])
    d.setdefault("core_characters", [])
    chars = need(d, "characters", list)
    for c in chars:
        if not isinstance(c, dict) or not str(c.get("name", "")).strip():
            raise ParseError("character without name")
    need(d, "taboos", list)
    need(d, "core_characters", list)
    return d
