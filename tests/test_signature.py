"""角色的招牌能力与成长阶段(路线 58)。

2026-10-03 用户:要能写出《海贼王》《火影》《死神》那种故事——那三部里每个重要角色都有招牌能力
(恶魔果实/忍术/斩魄刀),有名字与规则、随剧情进阶。此前账本里只有一段自由文本的"能力",模型就会临时给主角万能能力。
"""
from huaben import repo
from huaben.context import load_context
from huaben.pipeline.ledger_apply import apply_ledger, merge_character
from huaben.pipeline.normalize import normalize_character, normalize_ledger
from huaben.pipeline.prompts import ledger_messages, outline_messages, write_messages
from huaben.render import render_character
from huaben.signature import advance, normalize_signature, render

OUTLINE = {"title": "T", "outline": "事", "characters": [], "foreshadows": [], "planned_reversals": [], "hook": "钩"}


def test_normalize_signature_forgiving():
    assert normalize_signature(None) == {} and normalize_signature("乱写") == {"name": "乱写", "rule": "", "stage": "", "next": ""}
    assert normalize_signature({"name": " 写轮眼 ", "rule": "拷贝", "stage": "一勾玉"})["name"] == "写轮眼"
    assert normalize_signature({"rule": "没有名字"}) == {}  # 没名字 = 还没定招牌


def test_render_and_advance():
    sig = {"name": "写轮眼", "rule": "看穿并复制", "stage": "一勾玉", "next": "三勾玉"}
    assert "招牌:写轮眼" in render(sig) and "一勾玉" in render(sig) and "下一阶:三勾玉" in render(sig)
    assert render({}) == ""
    assert advance({"name": "写轮眼", "stage": "一勾玉"}, {"name": "写轮眼", "stage": "三勾玉"}) is True
    assert advance({"name": "写轮眼", "stage": "三勾玉"}, {"name": "写轮眼", "stage": "三勾玉"}) is False
    assert advance({}, {"name": "写轮眼", "stage": "一勾玉"}) is True  # 首次显露也算一次推进


def test_empty_signature_never_wipes_existing():
    """模型给空对象当"没变化":不能因此丢掉已经定下的招牌(与人物其余字段同一规则)。"""
    existing = {"name": "沈照", "alive": True, "location": "", "abilities": "", "relations": "", "knows": [],
                "core": True, "profile": "", "signature": {"name": "断水", "rule": "斩断", "stage": "初式", "next": ""}}
    merged = merge_character(existing, normalize_character({"name": "沈照", "signature": {}}))
    assert merged["signature"]["name"] == "断水"
    changed = merge_character(existing, normalize_character({"name": "沈照", "location": "山门"}))
    assert changed["signature"]["name"] == "断水" and changed["location"] == "山门"


def test_signature_is_logged_and_rendered(conn):
    bid = repo.create_book(conn, "书")
    vid = repo.create_volume(conn, bid, 1, status="active")
    cid = repo.create_chapter(conn, bid, vid, 1)
    led = normalize_ledger({"summary": "s", "foreshadows_new": [], "foreshadows_update": [], "facts": [],
                            "contradictions": [], "characters": [
                                {"name": "周小满", "signature": {"name": "听风耳", "rule": "听三里内私语",
                                                                 "stage": "初开", "next": "辨心音"}}]})
    warnings = apply_ledger(conn, bid, cid, 1, led)
    c = repo.list_characters(conn, bid)[0]
    assert c["signature"]["name"] == "听风耳"
    assert "招牌:听风耳" in render_character(c)

    # 进阶要留痕(爽点,不该被静默覆盖)
    led2 = normalize_ledger({"summary": "s", "foreshadows_new": [], "foreshadows_update": [], "facts": [],
                             "contradictions": [], "characters": [
                                 {"name": "周小满", "signature": {"name": "听风耳", "rule": "听三里内私语",
                                                                  "stage": "辨心音"}}]})
    w2 = apply_ledger(conn, bid, cid, 2, led2)
    assert any("进阶" in w and "辨心音" in w for w in w2)


def test_ledger_schema_and_prompts_ask_for_signature(conn):
    from huaben.pipeline.prompts import LEDGER_SCHEMA
    assert '"signature"' in LEDGER_SCHEMA and "招牌能力" in LEDGER_SCHEMA
    bid = repo.create_book(conn, "书")
    repo.create_volume(conn, bid, 1, status="active")
    ctx = load_context(conn, bid)
    assert "招牌能力" in write_messages(ctx, OUTLINE, 1000)[1]["content"]
    assert "招牌能力" in outline_messages(ctx)[1]["content"]
    assert "招牌能力" in ledger_messages(ctx, OUTLINE, "正文")[1]["content"]
