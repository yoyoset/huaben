"""伏笔分大小:短线 / 中线 / 长线。纯函数。

为什么(2026-10-02 用户:"伏笔太死,有的该很长、有的该很短,要有分类"):生产库《杂役仙尊》14 章埋了 23 条伏笔,
只收了 1 条(还是"明天再来"这种约定);"明天赴约"和"女主身世"记成一模一样的"后续章节揭示"——
小钩子拿不到及时兑现的爽感,大谜团也分不出轻重,只会越堆越多。
"""

SCALES = ("short", "medium", "long")
DEFAULT = "medium"  # 旧数据与模型没填时:中线(本卷内收)最不容易出错
LABEL = {"short": "短线", "medium": "中线", "long": "长线"}
RULE = {
    "short": "3~5 章内回收:眼前的悬念、约定、小谜,读者很快就该拿到答案",
    "medium": "本卷内回收:本卷剧情弧上的谜团与冲突",
    "long": "跨卷甚至到全书结尾才揭开:身世、主线大谜、世界真相;每次只给一点线索,不提前揭底",
}
SHORT_DUE, SHORT_OVERDUE = 3, 6  # 短线:埋下第 3 章起该收,第 6 章起算拖欠
MEDIUM_DUE_LEFT = 3              # 中线:本卷只剩这么多章时该收
OPEN_LIMIT = 10                  # 未收的短线+中线超过这个数:先还账,不再开新的中长线

_ALIASES = {
    "短": "short", "短线": "short", "短期": "short", "小": "short", "小伏笔": "short", "short-term": "short",
    "中": "medium", "中线": "medium", "中期": "medium", "mid": "medium", "middle": "medium",
    "长": "long", "长线": "long", "长期": "long", "大": "long", "大伏笔": "long", "主线": "long", "long-term": "long",
}


def normalize_scale(value) -> str:
    s = str(value or "").strip().lower()
    s = _ALIASES.get(s, s)
    return s if s in SCALES else DEFAULT


def due_state(f: dict, now_idx: int, volume_left: int | None, volume_first: int | None) -> str:
    """early(还早)/ due(该收了)/ overdue(拖欠)/ hold(长线:只推进不揭底)。
    volume_left:写完本章后本卷还剩几章;volume_first:本卷第一章的章号(没有进行中的卷时传 None)。"""
    scale = normalize_scale(f.get("scale"))
    age = now_idx - f["planted_ch"]
    if scale == "short":
        return "overdue" if age >= SHORT_OVERDUE else "due" if age >= SHORT_DUE else "early"
    if scale == "medium":
        if volume_first is not None and f["planted_ch"] < volume_first:
            return "overdue"  # 上一卷埋的中线没收:已经拖过卷了
        return "due" if volume_left is not None and volume_left <= MEDIUM_DUE_LEFT else "early"
    return "hold"


def tag(f: dict, state: str) -> str:
    """渲染进提示词的标签,如 [短线·该收了]。"""
    suffix = {"due": "·该收了", "overdue": "·已拖欠,尽快收", "hold": "·只推进不揭底"}.get(state, "")
    return f"[{LABEL[normalize_scale(f.get('scale'))]}{suffix}]"


def planting_rule(open_fs: list[dict], due_ids: list[int]) -> str:
    """章纲提示里的伏笔节奏要求。"""
    lines = ["伏笔分大小:" + ";".join(f"{LABEL[s]}={RULE[s]}" for s in SCALES) + "。"]
    if due_ids:
        lines.append("以下伏笔已到期,本章至少实打实地回收一条(给出答案,不是再加一层谜):"
                     + "、".join(f"#{i}" for i in due_ids) + "。")
    small = sum(1 for f in open_fs if normalize_scale(f.get("scale")) != "long")
    if small > OPEN_LIMIT:
        lines.append(f"未回收的短线+中线伏笔已有 {small} 条(超过 {OPEN_LIMIT}):本章以回收为主,不要再埋新的中线或长线伏笔。")
    return "\n".join(lines)
