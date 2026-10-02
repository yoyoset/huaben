"""从模型输出里取出 JSON 对象。纯函数。

模型常把 JSON 包在 ```json 围栏里或前后加话,这里容忍;取不出对象则抛 ParseError。
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


def need(data: dict, key: str, typ):
    if not isinstance(data.get(key), typ):
        raise ParseError(f"field {key!r} missing or not {typ.__name__}")
    return data[key]
