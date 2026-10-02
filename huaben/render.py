"""分层记忆·渲染:StoryContext → prompt 文本。纯函数,不碰数据库。"""
from .context import StoryContext, select_foreshadows, select_ledger
from .foreshadow_scale import due_state, tag


def _lines(items: list[str]) -> str:
    return "\n".join(items) if items else "(无)"


def render_character(c: dict, with_profile: bool = True) -> str:
    """with_profile:圣经人物卡里已有此人时不重复带人设,只带现状。"""
    state = "存活" if c["alive"] else "已死亡"
    parts = [f"- {c['name']}({state})"]
    if with_profile and c.get("profile"):
        parts.append(f"人设:{c['profile']}")
    if c["location"]:
        parts.append(f"位置:{c['location']}")
    if c["abilities"]:
        parts.append(f"能力:{c['abilities']}")
    if c["relations"]:
        parts.append(f"关系:{c['relations']}")
    if c["knows"]:
        parts.append("知道:" + "、".join(c["knows"]))
    return ";".join(parts)


def render_bible(bible: dict) -> str:
    chars = bible.get("characters") or []
    char_lines = [f"- {c.get('name', '?')}:{c.get('role', '')} {c.get('traits', '')}".rstrip() for c in chars]
    parts = [
        f"【世界观与规则】\n{bible.get('world') or '(未设定)'}",
        f"【人物卡】\n{_lines(char_lines)}",
    ]
    if bible.get("style_fingerprint"):
        parts.append(f"【风格指纹】\n{bible['style_fingerprint']}")
    if bible.get("taboos"):
        parts.append("【雷点(绝对不写)】\n" + _lines([f"- {t}" for t in bible["taboos"]]))
    return "\n\n".join(parts)


def render_style_samples(bible: dict) -> str:
    samples = bible.get("style_samples") or []
    if not samples:
        return ""
    body = "\n\n".join(f"〔样章片段{i}〕\n{s}" for i, s in enumerate(samples, 1))
    return f"【文风样章(模仿其语感、节奏、句式,不要照抄情节与专名)】\n{body}"


def volume_progress(ctx: StoryContext) -> str:
    """卷按章数封存,所以写每章都必须知道"本卷第几章、还剩几章",否则剧情弧与封卷时机脱节。"""
    target = ctx.volume["target_chapters"]
    pos = ctx.volume_done + 1
    return f"本卷进度:即将写本卷第 {pos}/{target} 章(写完本章后本卷还剩 {max(target - pos, 0)} 章)"


def render_foreshadow(f: dict, now_idx: int | None = None, state: str = "") -> str:
    age = f"(已埋 {now_idx - f['planted_ch']} 章)" if now_idx else ""
    plan = f"(计划:{f['payoff_plan']})" if f["payoff_plan"] else ""
    return f"- #{f['id']} {tag(f, state)} 第{f['planted_ch']}章埋{age}:{f['content']}{plan} [{f['status']}]"


def foreshadow_states(ctx: StoryContext) -> dict[int, str]:
    """每条未收伏笔此刻的状态:还早 / 该收了 / 拖欠 / 长线只推进(规则见 foreshadow_scale)。"""
    left = first = None
    if ctx.volume:
        left = max(ctx.volume["target_chapters"] - (ctx.volume_done + 1), 0)
        first = ctx.next_idx - ctx.volume_done
    return {f["id"]: due_state(f, ctx.next_idx, left, first) for f in ctx.foreshadows}


def due_foreshadow_ids(ctx: StoryContext) -> list[int]:
    """该收的伏笔编号:拖欠的在前,同类里埋得早的在前。"""
    states = foreshadow_states(ctx)
    due = [f for f in ctx.foreshadows if states[f["id"]] in ("due", "overdue")]
    due.sort(key=lambda f: (states[f["id"]] != "overdue", f["planted_ch"], f["id"]))
    return [f["id"] for f in due]


def _resolve_targets(ctx: StoryContext) -> str:
    """本卷计划要收的伏笔:按编号对上账本内容;已收的标注出来。"""
    open_by_id = {f["id"]: f for f in ctx.foreshadows}
    items = [f"#{i} {open_by_id[i]['content']}" if i in open_by_id else f"#{i}(已回收)"
             for i in ctx.volume["resolve"] if isinstance(i, int)]
    return "、".join(items) or "无"


def render_memory(ctx: StoryContext, scope: str = "", focus_ids=()) -> str:
    """分层记忆文本,顺序固定:梗概 → 往卷 → 本卷目标 → 本卷章摘要 → 账本。最近原文单独放,见 recent_text。
    scope:按需挑人物的检索文本(写作时 = 章纲;核对时 = 章纲 + 正文)。
    focus_ids:本章点名要推进/回收的伏笔编号(与本卷计划要收的一起优先展示)。
    """
    chars, facts = select_ledger(ctx.characters, ctx.facts, scope)
    parts = [f"【全书梗概】\n{ctx.book.get('synopsis') or '(尚无)'}"]
    if ctx.past_volume_summaries:
        parts.append("【往卷摘要】\n" + _lines([f"第{i}卷:{s}" for i, s in ctx.past_volume_summaries]))
    if ctx.volume:
        v = ctx.volume
        parts.append(f"【本卷(第{v['idx']}卷)目标】{v['goal']}\n{volume_progress(ctx)}\n节拍:"
                     + ("→".join(v["beats"]) or "(无)")
                     + "\n本卷要埋的伏笔:" + ("、".join(v["plant"]) or "无")
                     + "\n本卷要收的伏笔:" + _resolve_targets(ctx))
    parts.append("【本卷已发生(章摘要)】\n" + _lines(
        [f"第{i}章《{t}》:{s}" if t else f"第{i}章:{s}" for i, t, s in ctx.volume_chapter_summaries]))
    in_bible = {c.get("name") for c in (ctx.bible or {}).get("characters") or []}
    parts.append("【账本·人物现状(以此为准,不得矛盾)】\n" + _lines(
        [render_character(c, with_profile=c["name"] not in in_bible) for c in chars]))
    priority = set(focus_ids) | set(ctx.volume["resolve"] if ctx.volume else []) | set(due_foreshadow_ids(ctx))
    shown, hidden = select_foreshadows(ctx.foreshadows, priority)
    states = foreshadow_states(ctx)
    lines = [render_foreshadow(f, ctx.next_idx, states[f["id"]]) for f in shown]
    if hidden:
        lines.append(f"(另有 {hidden} 条较新的未回收伏笔,本章不必处理)")
    parts.append("【账本·未回收伏笔】\n" + _lines(lines))
    canon = (ctx.bible or {}).get("canon") or ""
    if canon:  # 往卷确立的事实在封卷时合并成定本;不截断,不会悄悄丢掉最早、最根本的设定
        parts.append(f"【账本·世界设定定本(往卷已确立,以此为准)】\n{canon}")
    parts.append("【账本·本卷新确立的事实】\n" + _lines([f"- {f['fact']}" for f in facts]))
    return "\n\n".join(parts)


def recent_text(ctx: StoryContext) -> str:
    if not ctx.recent:
        return "(这是开篇,没有前文)"
    return "\n\n".join(f"〔第{c['idx']}章《{c['title']}》〕\n{c['body']}" for c in ctx.recent)


# 写正文时不再给最近几章全文:2026-10-02 生产环境《杂役仙尊》第 13 章 6 稿里有 6 稿被"照抄前文"打回(11%~97%),
# 已定稿章之间的 12 字片段重合也从第 4 章的 0.4% 一路涨到第 14 章的 3.6%——前文全文就摆在提示里,模型越写越照搬。
# 剧情由章摘要交代,衔接只需要上一章的结尾。
HANDOFF_TAIL_CHARS = 1200


def handoff_text(ctx: StoryContext, tail_chars: int = HANDOFF_TAIL_CHARS) -> str:
    """作者用的"前情 + 上一章结尾":最近几章只给摘要,最后一章另附结尾原文。纯函数。"""
    if not ctx.recent:
        return "(这是开篇,没有前文)"
    lines = [f"第{c['idx']}章《{c['title']}》:{c['summary'] or '(无摘要)'}" for c in ctx.recent]
    last = ctx.recent[-1]
    tail = last["body"][-tail_chars:]
    cut = "……" if len(last["body"]) > tail_chars else ""
    return ("【紧接前情(章摘要)】\n" + "\n".join(lines)
            + f"\n\n【第{last['idx']}章结尾原文(本章从这里之后接着写;不要复述、不要改写这段)】\n{cut}{tail}")
