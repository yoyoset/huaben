"""各步骤的 LLM 指令。纯函数:StoryContext → messages。

两条来自前身踩坑的硬规则(docs/lessons-from-sillytavern.md):
- 关键约束放在 user 消息**末尾**(紧贴输出位置),关思考后远处的要求容易被丢;
- 示例里只用占位词("角色名"),不放任何专名 —— 示例文本也是 prompt,会被当成指令串进正文。
"""
from ..context import StoryContext
from ..render import recent_text, render_bible, render_memory, render_style_samples

OUTLINE_SCHEMA = """{
  "title": "本章标题(4~10 字)",
  "outline": "本章要发生什么,3~6 句,必须是一个完整剧情节拍",
  "characters": ["本章出场的人物名,须与账本/人物卡完全一致"],
  "foreshadows": [伏笔编号(整数),本章要推进或回收的],
  "planned_reversals": ["本章有意为之、会打破账本既有设定的反转;没有就留空数组"],
  "hook": "结尾钩子"
}"""

LEDGER_SCHEMA = """{
  "summary": "本章摘要,2~3 句,保留关键事件与因果",
  "characters": [{"name": "角色名", "alive": true, "location": "", "abilities": "", "relations": "",
                  "knows": ["该人物此刻知道的关键信息"], "core": false}],
  "foreshadows_new": [{"content": "本章新埋的伏笔", "payoff_plan": "打算何时、以何种方式回收"}],
  "foreshadows_update": [{"id": 伏笔编号(整数), "status": "progressing 或 resolved"}],
  "facts": ["本章新确立的世界事实"],
  "contradictions": [{"what": "与账本哪一条冲突、怎么冲突", "planned": 是否属于章纲 planned_reversals 里的有意反转(true/false)}]
}"""

_SYSTEM_EDITOR = "你是长篇连载小说的责任编辑,负责规划、记账与核对。严格只输出 JSON,不要任何解释或代码围栏。"


def pacing_rule(ctx: StoryContext) -> str:
    """按卷进度给节奏要求:卷在第 target 章自动封存,编辑必须让剧情弧恰好在那里收住。"""
    v = ctx.volume
    if v is None:
        return ""
    target, pos = v["target_chapters"], ctx.volume_done + 1
    if pos >= target:
        return "节奏:本章是本卷最后一章——必须完成本卷目标、回收本卷要收的伏笔,并留下通往下一卷的钩子。"
    left = target - pos
    if left <= max(2, target // 5):
        return f"节奏:本卷进入收尾阶段(本章之后只剩 {left} 章)——推向高潮、开始回收本卷伏笔,不要再开新的大支线。"
    beats = v["beats"] or []
    if not beats:
        return ""
    i = min(len(beats), ctx.volume_done * len(beats) // target + 1)
    return f"节奏:按进度,本章大约应推进第 {i}/{len(beats)} 个节拍「{beats[i - 1]}」。"


def outline_messages(ctx: StoryContext) -> list[dict]:
    user = (
        f"{render_bible(ctx.bible)}\n\n{render_memory(ctx)}\n\n"
        f"【最近原文(用于衔接)】\n{recent_text(ctx)}\n\n"
        f"请为第 {ctx.next_idx} 章写章纲工单。要求:紧扣本卷目标与节拍;伏笔该推进的推进、该收的收;"
        f"结尾留钩子;不得与账本冲突(除非明确写进 planned_reversals)。\n{pacing_rule(ctx)}\n"
        f"只输出如下结构的 JSON:\n{OUTLINE_SCHEMA}"
    )
    return [{"role": "system", "content": _SYSTEM_EDITOR}, {"role": "user", "content": user}]


def outline_scope(outline: dict) -> str:
    """章纲文字 + 出场人物:按需挑账本条目时的检索范围。"""
    return " ".join([outline["outline"], *outline.get("characters", [])])


def work_order(idx: int, outline: dict, open_foreshadows: list[dict] = ()) -> str:
    """作者看到的本章工单。编辑的计划要完整交到作者手上:
    - 本章要推进/回收的伏笔:否则"伏笔该推进的推进"只停留在编辑脑子里;
    - 有意反转:否则作者只看到"死者不得复活"之类的硬约束,会拒绝执行或写得自相矛盾。"""
    lines = [f"【本章工单】第 {idx} 章《{outline['title']}》", outline["outline"]]
    by_id = {f["id"]: f for f in open_foreshadows}
    threads = [by_id[i] for i in outline.get("foreshadows", []) if i in by_id]
    if threads:
        lines.append("本章要推进或回收的伏笔(要在情节里落到实处):")
        lines += [f"- #{f['id']} {f['content']}(第{f['planted_ch']}章埋)" for f in threads]
    if outline.get("planned_reversals"):
        lines.append("本章计划好的有意反转(必须写出来,并写得像伏笔回收、让读者恍然大悟,而不是像笔误):")
        lines += [f"- {r}" for r in outline["planned_reversals"]]
    lines.append(f"结尾钩子:{outline['hook']}")
    return "\n".join(lines)


def _consistency_rule(outline: dict) -> str:
    exception = "除工单列出的有意反转外," if outline.get("planned_reversals") else ""
    return f"2. {exception}严格遵守账本里的人物现状与世界事实,人名与设定不得漂移,死者不得复活;\n"


def write_messages(ctx: StoryContext, outline: dict, words: int, feedback: list[str] | None = None) -> list[dict]:
    system = (
        "你是长篇连载小说的作者,为一位读者私人连载。读者只读不参与,所以每章必须自成一个完整、好看的剧情节拍。\n\n"
        f"{render_bible(ctx.bible)}\n\n{render_style_samples(ctx.bible)}".rstrip()
    )
    parts = [
        render_memory(ctx, scope=outline_scope(outline), focus_ids=outline.get("foreshadows", [])),
        f"【最近原文(衔接文风与情绪)】\n{recent_text(ctx)}",
        work_order(ctx.next_idx, outline, ctx.foreshadows),
    ]
    if feedback:
        parts.append("【上一稿被编辑打回,以下问题必须修正】\n" + "\n".join(f"- {f}" for f in feedback))
    parts.append(  # 后置指令:紧贴输出位置
        f"现在写第 {ctx.next_idx} 章正文,约 {words} 字。硬性要求:\n"
        "1. 只输出正文,不要标题、不要解释、不要状态栏、不要任何前后缀;\n"
        + _consistency_rule(outline) +
        "3. 保持风格指纹与样章的语感;全文使用完整的中文标点;\n"
        "4. 结尾落在工单指定的钩子上。"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(parts)}]


def ledger_messages(ctx: StoryContext, outline: dict, body: str) -> list[dict]:
    user = (
        # 检索范围 = 章纲 + 正文:作者自己带进来的人(章纲没提)也必须拿账本状态核对,否则死人复活查不出
        f"{render_memory(ctx, scope=outline_scope(outline) + ' ' + body, focus_ids=outline.get('foreshadows', []))}\n\n"
        f"【本章章纲】\n{outline['outline']}\n本章有意为之的反转:{outline.get('planned_reversals') or '无'}\n"
        f"章纲点名要推进的伏笔:{'、'.join(f'#{i}' for i in outline.get('foreshadows', [])) or '无'}"
        "(正文里确有推进/回收的,务必在 foreshadows_update 登记)\n\n"
        f"【第 {ctx.next_idx} 章正文】\n{body}\n\n"
        "请完成入账与核对:提取摘要;更新出场人物的现状(生死/位置/能力/关系/知情);登记新伏笔与伏笔进展;"
        "登记新确立的世界事实;并核对正文是否与账本冲突(人名、生死、能力、知情范围、世界事实)。"
        "与账本冲突但属于章纲 planned_reversals 的,planned 填 true;其余冲突 planned 填 false。\n"
        f"只输出如下结构的 JSON:\n{LEDGER_SCHEMA}"
    )
    return [{"role": "system", "content": _SYSTEM_EDITOR}, {"role": "user", "content": user}]
