"""各步骤的 LLM 指令。纯函数:StoryContext → messages。

两条来自前身踩坑的硬规则(docs/lessons-from-sillytavern.md):
- 关键约束放在 user 消息**末尾**(紧贴输出位置),关思考后远处的要求容易被丢;
- 示例里只用占位词("角色名"),不放任何专名 —— 示例文本也是 prompt,会被当成指令串进正文。
"""
import json

from ..context import StoryContext
from ..craft import from_book, novelty_rule, render_craft
from ..devices import avoid_rule, from_rows, known_list
from ..foreshadow_scale import planting_rule
from ..render import due_foreshadow_ids, handoff_text, recent_text, render_bible, render_memory, render_style_samples
from .rules import (BOND_RULE, PAYOFF_RULE, REPETITION_RULE, SIGNATURE_RULE, SPEECH_RULE,  # noqa: F401
                    consistency_rule, pacing_rule, title_rule)

OUTLINE_SCHEMA = """{
  "title": "本章标题(4~10 字)",
  "outline": "本章要发生什么,3~6 句,必须是一个完整剧情节拍",
  "characters": ["本章出场的人物名,须与账本/人物卡完全一致"],
  "foreshadows": [伏笔编号(整数),本章要推进或回收的],
  "planned_reversals": ["本章有意为之、会打破账本既有设定的反转;没有就留空数组"],
  "payoff": "本章兑现:读者在这一章拿到什么——主角赢下了什么、谁吃了亏、哪里好笑、揭开了什么、关系往前走了哪一步;要具体,'获得新线索'不算",
  "novelty": "本章读者没见过的东西:用到世界观里哪一项原创设定(或按其规则新造一个),它在本章怎么起作用、怎么改变人物处境",
  "hook": "结尾钩子"
}"""

LEDGER_SCHEMA = """{
  "summary": "本章摘要,2~3 句,保留关键事件与因果",
  "characters": [{"name": "角色名(必填)。除 name 外只写本章有变化的字段,没变化的整个省略、不要写空值;alive 只在本章死亡时写",
                  "profile": "仅首次登场时写:身份、性格、说话方式,一句话",
                  "signature": {"name": "招牌能力名(仅当本章首次显露某人的招牌能力,或招牌能力进阶时写;没变化就整个省略)",
                                "rule": "一句话规则与代价/限制",
                                "stage": "当前形态/阶段(进阶时写新形态)",
                                "next": "下一个形态(可空)"},
                  "alive": false, "location": "新的所在地", "abilities": "新的能力状况",
                  "relations": "新的关系", "knows": ["该人物此刻知道的关键信息(写全量)"]}],
  "foreshadows_new": [{"content": "本章新埋的伏笔", "payoff_plan": "打算何时、以何种方式回收",
                       "scale": "short / medium / long / epic 四选一:short 短线 3~5 章内收(眼前的约定、小谜);medium 中线本卷内收;long 长线跨几卷(身世、主线谜团);epic 超长线全书级,终局才揭开"}],
  "foreshadows_update": [{"id": 伏笔编号(整数), "status": "progressing 或 resolved"}],
  "facts": ["本章新确立的世界事实"],
  "contradictions": [{"what": "读者当场能指出'这不可能/前后矛盾'的硬伤:与账本哪一条冲突,或正文内部哪个数字算错/前后不一;拿不准的不要写进来", "planned": 是否属于章纲 planned_reversals 里的有意反转(true/false)}],
  "editor_notes": ["供编辑参考、不影响定稿的观察:拿不准的疑点、建议、读感,以及本章里逐字重复的比喻/句子/口头禅(指出原句);不要写进 contradictions"],
  "devices": ["本章用来推动情节或制造悬念的手段(道具显灵、密信传话、偷听、异象等),每条 2~8 字;和【最近用过的手段】相同的沿用原名"]
}"""

_SYSTEM_EDITOR = "你是长篇连载小说的责任编辑,负责规划、记账与核对。严格只输出 JSON,不要任何解释或代码围栏。"


def recent_hooks(ctx: StoryContext) -> str:
    """最近几章的结尾钩子。2026-10-03《算尽仙朝》实测:第 1、3、5 章都以"算盘残片发烫、浮现一行字"收尾——
    编辑看不到自己前几章用过什么钩子,就会反复用同一招。纯函数;章纲解析不了的跳过。"""
    hooks = []
    for c in ctx.recent:
        try:
            hook = json.loads(c.get("outline") or "{}").get("hook", "")
        except ValueError:
            hook = ""
        if hook:
            hooks.append(f"- 第{c['idx']}章:{hook}")
    # 开场也列出来:《杂役仙尊》13、14 章开场几乎一样(雾、飞檐、枣树下练气),编辑看不到前几章怎么开的场
    openings = [f"- 第{c['idx']}章:{(c.get('body') or '').strip()[:40]}…" for c in ctx.recent if c.get("body")]
    out = ""
    if openings:
        out += ("最近几章的开场:\n" + "\n".join(openings)
                + "\n本章开场换一个时间、地点或动作;最近几章已经演过的场景、已经说出的信息不要再演一遍。\n")
    if hooks:
        out += ("最近几章的结尾钩子:\n" + "\n".join(hooks)
                + "\n本章结尾换一种钩子:不同的悬念来源、不同的人物或物件,不要再靠同一个道具或同一种异象收尾。\n")
    return out


def outline_messages(ctx: StoryContext) -> list[dict]:
    user = (
        f"{render_bible(ctx.bible)}\n\n{render_craft(from_book(ctx.book))}\n\n{render_memory(ctx)}\n\n"
        f"【最近原文(用于衔接)】\n{recent_text(ctx)}\n\n"
        f"请为第 {ctx.next_idx} 章写章纲工单。要求:紧扣本卷目标与节拍;伏笔该推进的推进、该收的收;"
        f"结尾留钩子;不得与账本冲突(除非明确写进 planned_reversals)。\n{PAYOFF_RULE}\n{BOND_RULE}\n{SIGNATURE_RULE}\n{SPEECH_RULE}\n{REPETITION_RULE}\n{title_rule(ctx.titles)}\n{pacing_rule(ctx)}\n"
        f"{planting_rule(ctx.foreshadows, due_foreshadow_ids(ctx))}\n{recent_hooks(ctx)}"
        f"{novelty_rule(from_book(ctx.book))}\n{avoid_rule(from_rows(ctx.recent))}\n"
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
    if outline.get("payoff"):
        lines.append(f"本章兑现(要写足、写在读者能感到痛快或好笑的地方,不能一笔带过):{outline['payoff']}")
    if outline.get("novelty"):
        lines.append(f"本章的新奇之处(写成读者看得见、摸得着的画面,让它推动情节;不要写成解释设定):{outline['novelty']}")
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
        handoff_text(ctx),
        work_order(ctx.next_idx, outline, ctx.foreshadows),
        render_craft(from_book(ctx.book)),  # 写法放在工单后、硬性要求前:离输出位置近,关思考的模型才不会丢
        avoid_rule(from_rows(ctx.recent)),  # 作者也要知道:章纲没写的地方,别顺手又让同一个道具出场
    ]
    parts = [p for p in parts if p]
    if feedback:
        parts.append("【上一稿被编辑打回,以下问题必须修正】\n" + "\n".join(f"- {f}" for f in feedback))
    parts.append(  # 后置指令:紧贴输出位置
        f"现在写第 {ctx.next_idx} 章正文,约 {words} 字。硬性要求:\n"
        "1. 只输出正文,不要标题、不要解释、不要状态栏、不要任何前后缀;\n"
        + consistency_rule(outline) +
        "3. 按【写法设定】写,保持风格指纹与样章的语感;全文使用完整的中文标点;\n"
        # 2026-10-03 读生产书:《算尽仙朝》整屏抽成数字,读者跟不上,且第 9 章说等比、第 10 章说等差
        "4. 推理、算账写给读者看得懂:一处推理只亮一两个关键数字,结论用一句人话点破(谁在搞鬼、怎么搞的),不要整屏罗列数字;"
        "账本里已有的数字照用,不要改;\n"
        + SIGNATURE_RULE + "\n"
        + SPEECH_RULE + "\n"
        + REPETITION_RULE + "\n"
        + BOND_RULE + "\n"
        "6. 结尾落在工单指定的钩子上。"
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
        f"【最近用过的手段】{known_list(from_rows(ctx.recent))}\n\n"
        "请完成入账与核对:提取摘要;更新出场人物的现状(生死/位置/能力/关系/知情);登记新伏笔与伏笔进展;"
        "反复出场的人物在本章首次显露招牌能力、或招牌能力进阶时,在 signature 里登记(有名有姓、一句话规则与代价、当前形态);"
        "登记新确立的世界事实——正文里出现、后文可能再用到的具体数字(数量、价格、比例、日期)也作为事实登记,写清它指什么;"
        "并核对正文是否与账本冲突(人名、生死、能力、知情范围、世界事实、已登记的数字),"
        "以及正文内部:同一个数前后是否一致、算术是否算对(例如\"一瓶十粒,三瓶九十粒\"就是算错——"
        "它自称一瓶十粒,却又说三瓶九十粒,前后对不上,是硬伤,不是\"拿不准\")。"
        "只报本章正文造成的问题;账本里早就存在的不一致不是本章的错,不要报(否则重写多少稿也改不掉)。"
        "判断标准:读者当场能指出\"这不可能/前后矛盾\"的硬伤(含正文自己声明的数乘不上、加减不上)写进 contradictions"
        "(与账本冲突但属于章纲 planned_reversals 的,planned 填 true;其余含正文内部数字错误的,planned 填 false)。"
        "拿不准的疑点、建议、读感、时间线略不顺、需要后续澄清的,写进 editor_notes,不要写进 contradictions"
        "(不影响定稿,只供编辑参考)。本章里逐字重复的比喻/句子/口头禅,也写进 editor_notes 并指出原句。\n"
        f"只输出如下结构的 JSON:\n{LEDGER_SCHEMA}"
    )
    return [{"role": "system", "content": _SYSTEM_EDITOR}, {"role": "user", "content": user}]
