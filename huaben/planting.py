"""伏笔先知道答案再埋:章纲计划要埋的那一条(plant)才登记,入账捡出来的一律只留痕。纯函数与常量。

为什么(2026-10-03 用户:"有时候很尬——为了埋伏笔而埋伏笔,这个伏笔完全毫无意义,很奇怪。能不能更专业一点。"):
架构方查生产,《算尽仙朝》13 章登记了 29 条伏笔、一条都没收;《杂役仙尊》14 章 23 条、只收了 1 条,平均每章新埋 2 条。
内容大量是"枣树根旁湿土有两道浅浅鞋尖蹭印""破窗边青灰布条无风却晃动""铜钱边多了一道细刮痕,刮痕里嵌有青灰色粉末",
"回收计划"几乎全是套话"后续章节揭示……身份",没有一条写了答案是什么。原因三个,都在流程里:
1. 伏笔不是计划出来的,是事后捡出来的——章纲没有"本章埋什么"这一栏,写完入账那一步才让模型"登记新伏笔",
   正文里任何一个没解释的细节都被登记成伏笔,写的时候根本没人知道它的答案。
2. 每章都要"结尾留钩子",最省事的钩子就是凭空冒出一个神秘物件/记号/纸条/人影,于是每章一条新"伏笔"。
3. "欠账太多就不许再埋"只是章纲提示里的一句话,登记发生在入账,程序上没有任何限制,所以 29 条照埋不误。

专业的做法:伏笔是作者**已经知道真相**之后,故意提前露出的一角。不知道答案的"神秘细节"不是伏笔,是欠读者的账。
"""
from .foreshadow_scale import normalize_scale

OPEN_TOTAL_LIMIT = 12  # 未回收伏笔(不分大小)超过这个数:先还账,一条新的都不登记

PLANT_SCHEMA = ('  "plant": {"content": "本章要埋的伏笔:读者会看到什么", '
                '"truth": "它背后的真相是什么、将来怎么改变剧情(你必须现在就知道答案;只有编辑和作者知道,不写进正文)", '
                '"scale": "short / medium / long / epic"},')

PLANT_RULE = ("伏笔是你已经知道真相之后,故意提前露出的一角——不知道答案的神秘细节不是伏笔,是欠读者的账。"
              "plant 最多一条,多数章应为 null;只有当你说得出它背后的真相(truth),而且这个真相会改变后面的剧情时才埋。"
              "优先埋卷计划里【本卷要埋的伏笔】列出的那些。不要埋:来历不明的痕迹、记号、粉末、布条、脚印、"
              "又一张纸条、一闪而过的人影——除非你现在就能在 truth 里写出它是谁留的、为什么。")

HOOK_RULE = ("结尾钩子用已有的东西:本章冲突的后果、已有伏笔往前走了一步、马上要来的危险或抉择。"
             "不要为了钩子新造一个神秘物件、神秘人或神秘记号。")

NO_PLANT_RULE = "未回收的伏笔已有 {n} 条(上限 {limit}):本章 plant 必须为 null,把篇幅用在回收和推进已有的伏笔上。"


def normalize_plant(raw) -> dict | None:
    """章纲里的 plant → 合法形状;缺 content 或 truth 就是 None(说不出真相的不算伏笔)。"""
    if not isinstance(raw, dict):
        return None
    content, truth = str(raw.get("content") or "").strip(), str(raw.get("truth") or "").strip()
    if not content or not truth:
        return None
    return {"content": content, "truth": truth, "scale": normalize_scale(raw.get("scale")),
            "key": str(raw.get("key") or "").strip()}


def plant_rule(open_count: int) -> str:
    """章纲提示里的伏笔要求:欠账超限时改成"本章不许埋"。"""
    if open_count > OPEN_TOTAL_LIMIT:
        return NO_PLANT_RULE.format(n=open_count, limit=OPEN_TOTAL_LIMIT)
    return PLANT_RULE


def to_register(plant: dict | None, open_count: int, extracted: list[dict],
                scripted: bool = False) -> tuple[list[dict], list[str]]:
    """→ (要登记进账本的新伏笔, 运行记录)。只登记章纲计划的那一条;入账捡出来的(extracted)一律不登记、只留痕。
    scripted=True(剧本书):剧本里埋多少是架构方算过的,不受 OPEN_TOTAL_LIMIT 限制。"""
    notes = [f"计划外的悬念(未登记为伏笔):{f['content'][:60]}" for f in extracted]
    if plant is None:
        return [], notes
    if not scripted and open_count > OPEN_TOTAL_LIMIT:
        return [], notes + [f"未回收伏笔 {open_count} 条超过上限 {OPEN_TOTAL_LIMIT},章纲计划的伏笔未登记:{plant['content'][:60]}"]
    return [{"content": plant["content"], "payoff_plan": plant["truth"], "scale": plant["scale"],
             "key": plant.get("key", "")}], notes
