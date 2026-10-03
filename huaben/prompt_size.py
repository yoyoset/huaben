"""一次生成的 prompt 体量观测(路线 68)。纯函数。

为什么:分层记忆的设计目标是"第 500 章的 prompt 体量和第 50 章差不多",但此前没有任何观测——
定本(canon)只测了它自己,一次生成实际塞进多少字没人看得到。连载到几百章后,如果某个环节悄悄膨胀
(定本没去重、伏笔/人物越带越多),成本会一路涨、模型也更容易丢约束。这里把"下一章实际会发的 prompt"量出来。
"""
from .pipeline import prompts
from .context import StoryContext

# 观测线:默认单章约 2500 字正文,prompt 比正文长几倍是正常的(分层记忆 + 账本 + 工单);
# 超过这条线说明某个环节大概率没压住,值得看一眼(只告警、不截断——截断正是被否掉过的做法)。
WARN_CHARS = 24_000


def measure(ctx: StoryContext, words: int | None = None, outline: dict | None = None) -> dict:
    """量章纲与正文两条 prompt 的字符数与粗略 token 数。outline 缺省用一个最小工单(只量框架+记忆)。
    中文约 1~1.5 token/字,这里按 1.0 粗估,只作相对观测,不当计费依据。"""
    words = words or 2500
    o = outline or {"title": "T", "outline": "（工单待生成）", "characters": [], "foreshadows": [],
                    "planned_reversals": [], "hook": ""}
    outline_msgs = prompts.outline_messages(ctx)
    write_msgs = prompts.write_messages(ctx, o, words)
    return {
        "outline_chars": _chars(outline_msgs),
        "write_chars": _chars(write_msgs),
        "write_tokens_est": _chars(write_msgs),
        "warn_chars": WARN_CHARS,
        "too_long": _chars(write_msgs) > WARN_CHARS,
    }


def _chars(messages: list[dict]) -> int:
    return sum(len(m.get("content") or "") for m in messages)
