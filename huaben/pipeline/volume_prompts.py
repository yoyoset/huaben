"""卷级编辑步骤的指令:卷规划、封卷。约束同 prompts.py:关键要求放末尾,示例不放专名。"""
from ..context import StoryContext
from ..render import render_bible, render_memory

PLAN_SCHEMA = """{
  "goal": "本卷要达成的目标,1~2 句",
  "beats": ["节拍,按先后顺序,5~10 条,每条一句话"],
  "plant": ["本卷要新埋的伏笔"],
  "resolve": ["本卷要回收的伏笔(优先从账本未回收伏笔里选)"],
  "target_chapters": 本卷计划章数(整数,通常 20~40)
}"""

SEAL_SCHEMA = """{
  "volume_summary": "本卷摘要,一段话(150~300 字):发生了什么、人物关系与力量格局的变化、留下的悬念",
  "synopsis": "更新后的全书梗概(300~600 字):这是什么故事、至今走到哪了"
}"""

_SYSTEM = "你是长篇连载小说的责任编辑。严格只输出 JSON,不要任何解释或代码围栏。"


def plan_messages(ctx: StoryContext, idx: int) -> list[dict]:
    user = (
        f"{render_bible(ctx.bible)}\n\n{render_memory(ctx)}\n\n"
        f"请规划第 {idx} 卷。要求:有清晰的卷内目标和起承转合;未回收的伏笔要有计划地收,"
        f"同时埋下新的;与已有人物现状和世界事实自洽;符合雷点与风格设定;节奏紧凑,每个节拍都能撑起爽点或悬念。\n"
        f"只输出如下结构的 JSON:\n{PLAN_SCHEMA}"
    )
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]


def seal_messages(ctx: StoryContext, volume: dict, chapters: list[dict]) -> list[dict]:
    summaries = "\n".join(f"第{c['idx']}章《{c['title']}》:{c['summary']}" for c in chapters)
    user = (
        f"【旧全书梗概】\n{ctx.book.get('synopsis') or '(尚无)'}\n\n"
        f"【本卷(第{volume['idx']}卷)目标】{volume['goal']}\n【本卷章摘要】\n{summaries}\n\n"
        "本卷已经写完,请封卷:压缩成卷摘要,并把这一卷融入全书梗概。保留会影响后续的事实、人物状态变化和悬念。\n"
        f"只输出如下结构的 JSON:\n{SEAL_SCHEMA}"
    )
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]
