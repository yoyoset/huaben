"""一卷 = 一段征战。纯函数。

为什么(2026-10-03 用户):"这种故事吸引人,就是隔一段时间制造一个新的矛盾和敌人,征战,最后胜利,只是呈现方式多种多样。"
骨架对,但同样的骨架有的越看越上头、有的第三段就腻——差别在:对手有没有自己的道理、赌注是不是具体、
每段的打法是不是不一样、有没有跌到谷底、赢了付出什么、赢完什么变了、离全书的大谜团是不是更近一步。
此前卷规划只有 目标/节拍/伏笔,这些都没有被要求,编辑就只会写"主角遇到困难、克服困难"。
"""
MODES = ("正面对决", "智斗骗局", "破案追查", "朝堂博弈", "逃亡求生", "比赛竞技", "谈判结盟",
         "潜入夺取", "守城保卫", "探索奇境", "内部清洗", "营救")
FIELDS = ("antagonist", "motive", "edge", "stakes", "mode", "low_point", "cost", "change", "thread")
REQUIRED = ("antagonist", "motive", "stakes", "low_point", "cost", "change")

ARC_SCHEMA = """{
    "antagonist": "本卷的对手:一个人、一个势力或一种处境",
    "motive": "对手自己的道理:站在他的角度,他做的事并不荒唐",
    "edge": "对手凭什么压得住主角(主角缺的是什么)",
    "stakes": "主角输了会具体失去什么(某个人、某样东西、某种处境)",
    "mode": "这一段怎么打,从这些里选一个:%s",
    "low_point_beat": 谷底落在第几个节拍(整数),
    "low_point": "谷底:主角被逼到最低处时发生了什么",
    "cost": "胜利的代价:赢了,但失去或付出了什么",
    "change": "卷末什么变了:主角、人物关系、势力格局,或读者对这个世界的认识",
    "thread": "本卷推进哪条长线/超长线伏笔、推进到哪一步(不揭底)"
  }""" % "、".join(MODES)


def normalize_arc(d, beat_count: int) -> dict | None:
    """模型给的 arc → 合法形状;缺关键项返回 None(调用方当作"这次没规划出来")。谷底节拍夹到 1..节拍数。"""
    if not isinstance(d, dict):
        return None
    arc = {k: str(d.get(k) or "").strip() for k in FIELDS}
    if any(not arc[k] for k in REQUIRED):
        return None
    try:
        beat = int(d.get("low_point_beat"))
    except (TypeError, ValueError):
        beat = max(1, beat_count * 2 // 3)  # 没给就放在三分之二处:起承之后、高潮之前
    arc["low_point_beat"] = min(max(beat, 1), max(beat_count, 1))
    return arc


def render_arc(arc: dict | None) -> str:
    if not arc:
        return ""
    lines = [f"对手:{arc['antagonist']}(他的道理:{arc['motive']}" + (f";凭什么压得住主角:{arc['edge']}" if arc.get("edge") else "") + ")",
             f"赌注:{arc['stakes']}"]
    if arc.get("mode"):
        lines.append(f"打法:{arc['mode']}")
    lines += [f"谷底(第 {arc['low_point_beat']} 个节拍):{arc['low_point']}", f"胜利的代价:{arc['cost']}",
              f"卷末的变化:{arc['change']}"]
    if arc.get("thread"):
        lines.append(f"推进的长线:{arc['thread']}")
    return "本卷是一段征战——\n" + "\n".join(f"  {x}" for x in lines)


def arc_pacing(arc: dict | None, beat_index: int, chapters_left: int) -> str:
    """按进度提醒征战结构里此刻该落地的那一项。beat_index:本章大约在第几个节拍(从 1 起)。"""
    if not arc:
        return ""
    if chapters_left <= 0:
        return f"征战收尾:胜利的代价必须在本章落地({arc['cost']});写出卷末的变化({arc['change']})。"
    if beat_index == arc["low_point_beat"]:
        return f"本章在本卷谷底附近:{arc['low_point']}——把主角逼到最低处,不要在同一章轻易翻盘。"
    if beat_index < arc["low_point_beat"]:
        return f"谷底还没到:对手要一步步占上风(凭的是:{arc.get('edge') or '他的优势'}),主角的胜算在变小。"
    return f"谷底之后的翻盘要有代价,并且是靠主角的本事挣来的,不是对手突然犯蠢;代价:{arc['cost']}。"


def past_modes(volumes: list[dict]) -> list[str]:
    """往卷用过的打法(按卷序),规划新卷时要求换一种。"""
    return [f"第{v['idx']}卷:{v['arc']['mode']}" for v in volumes if (v.get("arc") or {}).get("mode")]
