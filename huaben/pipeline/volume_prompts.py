"""卷级编辑步骤的指令:卷规划、封卷。约束同 prompts.py:关键要求放末尾,示例不放专名。"""
from ..arc import ARC_SCHEMA, world_ladder_rule
from ..beat_budget import BUDGET_RULE
from ..context import StoryContext
from ..craft import from_book, render_craft
from ..render import render_bible, render_foreshadow, render_memory
from ..rival import advance_rule, from_bible as rivals_from_bible
from ..theme import advance_rule as theme_advance_rule
from .rules import BOND_RULE

PLAN_SCHEMA = """{
  "goal": "本卷要达成的目标,1~2 句",
  "beats": ["节拍,按先后顺序,5~10 条,每条一句话"],
  "beat_chapters": [每个节拍给几章(整数),与 beats 一一对应、等长,不要平均分],
  "plant": ["本卷要新埋的伏笔"],
  "resolve": [本卷要回收的伏笔编号(整数,只能从下面【可回收的伏笔】里选)],
  "target_chapters": 本卷计划章数(整数,通常 20~40),
  "arc": %s
}""" % ARC_SCHEMA

PLAN_LIST_LIMIT = 30   # 规划时展示的未回收伏笔上限(最早埋下的优先)
BACKLOG_WARN = 8       # 未回收伏笔超过这个数,本卷应以回收为主

SEAL_SCHEMA = """{
  "volume_summary": "本卷摘要,一段话(150~300 字):发生了什么、人物关系与力量格局的变化、留下的悬念",
  "synopsis": "更新后的全书梗概(300~600 字):这是什么故事、至今走到哪了",
  "canon": "更新后的世界设定定本:把旧定本与本卷新确立的事实合并,去重、删掉已被剧情推翻的,要点式,每行一条"
}"""

_SYSTEM = "你是长篇连载小说的责任编辑。严格只输出 JSON,不要任何解释或代码围栏。"


def foreshadow_backlog(ctx: StoryContext, carried_ids=()) -> str:
    """规划用的伏笔清单:最早埋下的优先;上一卷计划要收却没收的单独点名。"""
    fs = sorted(ctx.foreshadows, key=lambda f: (f["planted_ch"], f["id"]))
    lines = [render_foreshadow(f, ctx.next_idx) for f in fs[:PLAN_LIST_LIMIT]]
    if len(fs) > PLAN_LIST_LIMIT:
        lines.append(f"(另有 {len(fs) - PLAN_LIST_LIMIT} 条较新的,本卷不必安排)")
    out = "【可回收的伏笔(全部未回收,按埋下先后)】\n" + ("\n".join(lines) or "(无)")
    carried = [f"#{i}" for i in carried_ids if any(f["id"] == i for f in fs)]
    if carried:
        out += "\n上一卷计划回收却没有收的:" + "、".join(carried) + "(本卷应优先安排)"
    if len(fs) > BACKLOG_WARN:
        out += f"\n未回收伏笔已积压 {len(fs)} 条:本卷以回收为主,新埋的不要超过 2 条。"
    return out


ARC_RULE = ("这一卷是一段征战(arc):一个有自己道理的对手、一个具体的赌注、一种打法;"
            "节拍里要有一次把主角逼到最低处的谷底,翻盘要靠主角的本事挣来、并且付出代价;卷末必须有东西变了;"
            "顺手推进一条长线或超长线伏笔,让读者离全书的大谜团近一步;"
            "world 写出本卷把读者的世界坐标推到哪一格——只升不降(更大的舞台、更高的势力层级,或这个世界更核心的真相)。"
            + BOND_RULE)


def plan_messages(ctx: StoryContext, idx: int, carried_ids=(), used_modes=(), used_worlds=(), used_rivals=()) -> list[dict]:
    """used_modes:往卷用过的打法(arc.past_modes),本卷换一种——连载腻人往往就是每段都一个打法。
    used_worlds:往卷的世界坐标(arc.past_worlds),本卷只升不降。used_rivals:往卷已推进的长期对手。"""
    modes = f"往卷的打法:{';'.join(used_modes)}。本卷换一种打法。\n" if used_modes else ""
    ladder = (world_ladder_rule(list(used_worlds)) + "\n") if used_worlds else ""
    rivals = advance_rule(rivals_from_bible(ctx.bible), list(used_rivals))
    rival_line = (rivals + "\n") if rivals else ""
    theme = theme_advance_rule(bool((ctx.bible or {}).get("theme") or (ctx.bible or {}).get("central_mystery")))
    theme_line = (theme + "\n") if theme else ""
    user = (
        f"{render_bible(ctx.bible)}\n\n{render_craft(from_book(ctx.book))}\n\n{render_memory(ctx)}\n\n"
        f"{foreshadow_backlog(ctx, carried_ids)}\n\n"
        f"请规划第 {idx} 卷。要求:有清晰的卷内目标和起承转合;未回收的伏笔要有计划地收,"
        f"同时埋下新的;与已有人物现状和世界事实自洽;符合雷点与风格设定;节奏紧凑,每个节拍都能撑起爽点或悬念;"
        f"叙事结构与伏笔布局按【写法设定】安排(例如多线交织就规划好各条线在哪些节拍汇合)。\n"
        f"{BUDGET_RULE}\n{ARC_RULE}\n{modes}{ladder}{rival_line}{theme_line}"
        f"只输出如下结构的 JSON:\n{PLAN_SCHEMA}"
    )
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]


def arc_messages(ctx: StoryContext, volume: dict, summaries: list[str], used_modes=(), used_worlds=(), used_rivals=()) -> list[dict]:
    """给已经在写的卷补征战结构(旧书升级用):节拍不改、已写的不改,只把这一段征战的骨架说清楚。"""
    beats = "\n".join(f"{i}. {b}" for i, b in enumerate(volume["beats"], 1))
    modes = f"往卷的打法:{';'.join(used_modes)}。本卷换一种打法。\n" if used_modes else ""
    ladder = (world_ladder_rule(list(used_worlds)) + "\n") if used_worlds else ""
    rivals = advance_rule(rivals_from_bible(ctx.bible), list(used_rivals))
    rival_line = (rivals + "\n") if rivals else ""
    theme = theme_advance_rule(bool((ctx.bible or {}).get("theme") or (ctx.bible or {}).get("central_mystery")))
    theme_line = (theme + "\n") if theme else ""
    user = (
        f"{render_bible(ctx.bible)}\n\n{render_craft(from_book(ctx.book))}\n\n"
        f"【本卷(第{volume['idx']}卷)目标】{volume['goal']}\n【本卷节拍】\n{beats}\n\n"
        f"【本卷已写章节】\n{chr(10).join(summaries) or '(还没有)'}\n\n"
        f"这一卷已经开始写,但还没有明确征战结构。{ARC_RULE}请在不改节拍、不与已写章节矛盾的前提下补出来。\n"
        f"{modes}{ladder}{rival_line}{theme_line}"
        f"只输出如下结构的 JSON:\n{ARC_SCHEMA}"
    )
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]


def seal_messages(ctx: StoryContext, volume: dict, chapters: list[dict]) -> list[dict]:
    summaries = "\n".join(f"第{c['idx']}章《{c['title']}》:{c['summary']}" for c in chapters)
    facts = "\n".join(f"- {f['fact']}" for f in ctx.facts) or "(无)"
    user = (
        f"【旧全书梗概】\n{ctx.book.get('synopsis') or '(尚无)'}\n\n"
        f"【旧世界设定定本】\n{(ctx.bible or {}).get('canon') or '(尚无)'}\n\n【本卷新确立的事实】\n{facts}\n\n"
        f"【本卷(第{volume['idx']}卷)目标】{volume['goal']}\n【本卷章摘要】\n{summaries}\n\n"
        "本卷已经写完,请封卷:压缩成卷摘要,把这一卷融入全书梗概,并把本卷新事实并入世界设定定本"
        "(定本之后会替代这些事实逐条进入写作 prompt,所以不能漏掉仍然成立的事实)。"
        "保留会影响后续的事实、人物状态变化和悬念。\n"
        f"只输出如下结构的 JSON:\n{SEAL_SCHEMA}"
    )
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]
