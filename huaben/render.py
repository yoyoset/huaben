"""分层记忆·渲染:StoryContext → prompt 文本。纯函数,不碰数据库。"""
from .context import StoryContext, select_ledger


def _lines(items: list[str]) -> str:
    return "\n".join(items) if items else "(无)"


def render_character(c: dict) -> str:
    state = "存活" if c["alive"] else "已死亡"
    parts = [f"- {c['name']}({state})"]
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


def render_memory(ctx: StoryContext, scope: str = "") -> str:
    """分层记忆文本,顺序固定:梗概 → 往卷 → 本卷目标 → 本卷章摘要 → 账本。最近原文单独放,见 recent_text。
    scope:按需挑账本条目的检索文本(写作时 = 章纲;核对时 = 章纲 + 正文)。
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
                     + "\n本卷要收的伏笔:" + ("、".join(v["resolve"]) or "无"))
    parts.append("【本卷已发生(章摘要)】\n" + _lines(
        [f"第{i}章《{t}》:{s}" if t else f"第{i}章:{s}" for i, t, s in ctx.volume_chapter_summaries]))
    parts.append("【账本·人物现状(以此为准,不得矛盾)】\n" + _lines([render_character(c) for c in chars]))
    parts.append("【账本·未回收伏笔】\n" + _lines(
        [f"- #{f['id']} 第{f['planted_ch']}章埋:{f['content']}"
         + (f"(计划:{f['payoff_plan']})" if f["payoff_plan"] else "")
         + f" [{f['status']}]" for f in ctx.foreshadows]))
    canon = (ctx.bible or {}).get("canon") or ""
    if canon:  # 往卷确立的事实在封卷时合并成定本;不截断,不会悄悄丢掉最早、最根本的设定
        parts.append(f"【账本·世界设定定本(往卷已确立,以此为准)】\n{canon}")
    parts.append("【账本·本卷新确立的事实】\n" + _lines([f"- {f['fact']}" for f in facts]))
    return "\n\n".join(parts)


def recent_text(ctx: StoryContext) -> str:
    if not ctx.recent:
        return "(这是开篇,没有前文)"
    return "\n\n".join(f"〔第{c['idx']}章《{c['title']}》〕\n{c['body']}" for c in ctx.recent)
