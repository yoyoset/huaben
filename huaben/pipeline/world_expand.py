"""给已经开书的书补充原创设定:只往世界观里加,不推翻已写的章节。

为什么(2026-10-03):《算尽仙朝》开书时读者说了四遍"放开想象力",世界观却是类型默认模板——当时定稿圣经没有任何
"要原创"的要求、温度还压在 0.5。新书开书时已按想象力档位处理(craft.world_brief);已经写了几章的书不能推倒重来,
所以做成"补充":在现有设定上加核心机制、地方、势力的原创细节,并且给已出场的元素(道具、能力)赋予独特的规则。
补充的内容以带日期的小标题追加在原世界观后面——原来的文字原样保留,想撤回删掉这一节即可。
"""
import datetime
import json

from .. import repo
from ..craft import WORLD_RULE, WORLD_TEMPERATURE, from_book, normalize_craft, render_craft
from ..llm import LLM
from .jsonout import ParseError, extract_json
from .llm_step import call_step

SYSTEM = "你是长篇连载小说的设定编辑。严格只输出 JSON,不要任何解释或代码围栏。"
SCHEMA = '{"additions": "要补充进世界观的原创设定,要点式,每条写清它怎么运作、代价或限制、会怎样卷入情节", ' \
         '"why": "一两句话:补充后这个世界和原来比新在哪里"}'


def expand_messages(bible: dict, synopsis: str, summaries: list[str], craft: dict) -> list[dict]:
    """纯函数:给设定编辑的指令。已写章节的摘要必须带上——补充的设定不能和读者已经读到的内容打架。"""
    written = "\n".join(summaries) or "(还没有写好的章)"
    user = (
        f"【现有世界观】\n{bible.get('world') or '(无)'}\n\n"
        f"【人物】\n{json.dumps(bible.get('characters') or [], ensure_ascii=False)}\n\n"
        f"【全书梗概】\n{synopsis or '(无)'}\n\n【已写章节摘要(补充的设定不能与之矛盾)】\n{written}\n\n"
        f"{render_craft(craft)}\n\n"
        "读者觉得现在的设定太套路、想象力不够。请在不推翻已写内容的前提下补充原创设定:"
        f"{WORLD_RULE}已经出场的元素(道具、能力、组织)可以赋予更独特的运作规则,但已经发生的事不能改。\n"
        f"只输出如下结构的 JSON:\n{SCHEMA}"
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def append_section(world: str, additions: str, today: str) -> str:
    """纯函数:补充内容追加在原世界观后面,带日期小标题;原文一字不动。"""
    return f"{world.rstrip()}\n\n【原创设定补充 {today}】\n{additions.strip()}"


def expand_world(conn, llm: LLM, book_id: int) -> dict:
    """调用一次模型,把补充写进圣经的 world。返回 {"additions", "why"} 给页面显示。"""
    book = repo.get_book(conn, book_id)
    bible = repo.get_bible(conn, book_id) or {}
    craft = from_book(book)
    summaries = [f"第{c['idx']}章《{c['title']}》:{c['summary']}" for c in repo.chapter_index(conn, book_id) if c["summary"]]
    level = normalize_craft(craft)["imagination"]
    res = call_step(conn, llm, book_id, None, "world", expand_messages(bible, book["synopsis"], summaries, craft),
                    json_mode=True, temperature=max(WORLD_TEMPERATURE[level], 0.8))
    data = extract_json(res.text)
    additions = str(data.get("additions") or "").strip()
    if not additions:
        raise ParseError("设定编辑没有给出补充内容")
    today = datetime.date.today().isoformat()
    repo.save_bible(conn, book_id, world=append_section(bible.get("world") or "", additions, today))
    return {"additions": additions, "why": str(data.get("why") or "").strip()}
