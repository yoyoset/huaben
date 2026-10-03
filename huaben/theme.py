"""故事的主题与核心谜团(路线 69)。纯函数。

为什么(2026-10-03 用户:要能写出《海贼王》《火影》《死神》那种故事):
那三部的超长线最后都指向一个"这本书到底在讲什么"的核心——OP 是自由的代价与继承的意志,
火影是羁绊与仇恨的循环,死神是死亡、告别与守护。系统里有超长线伏笔(epic),但没有告诉模型
"这些线最后要一起指向什么"。没有一个中心,超长线就只是拖得久,而不是有落点。
做法:开书圣经里明确写下 theme(这本书在讲什么)与 central_mystery(全书要揭开的那个核心谜团);
卷规划每一卷都要朝它推进一步;章纲提醒别忘了它。
"""
MAX_CHARS = 300


def normalize(theme: str, mystery: str) -> tuple[str, str]:
    return (str(theme or "").strip()[:MAX_CHARS], str(mystery or "").strip()[:MAX_CHARS])


def render(theme: str, mystery: str) -> str:
    """写进 prompt 的一段;两者都空时为空串(旧书不强行编造)。"""
    t, m = normalize(theme, mystery)
    if not t and not m:
        return ""
    lines = ["【故事的主题与核心谜团(全书的总纲)】"]
    if t:
        lines.append(f"主题(这本书到底在讲什么):{t}")
    if m:
        lines.append(f"核心谜团(全书最终要揭开、所有长线都要汇到它上面的那个谜):{m}")
    lines.append("每一卷都要朝它推进一步;超长线伏笔是它的碎片,平时只轻轻回响、不提前揭底,揭晓时要让读者重新理解前面的故事。")
    return "\n".join(lines)


def advance_rule(has: bool) -> str:
    """卷规划提示里的一句;圣经没写主题/核心谜团时为空,不强行编造。"""
    if not has:
        return ""
    return ("本卷要朝【故事的主题与核心谜团】推进一步:至少让读者多知道一点那个核心谜团,或让主题在本卷有一个新的侧面;"
            "推进要像揭开谜团的一角,而不是提前把底揭了。")
