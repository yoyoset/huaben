"""伏笔先知道答案再埋(T007):plant 纯函数 + 章纲/工单提示 + 定稿登记。"""
import json

from huaben import repo
from huaben.config import Settings
from huaben.context import load_context
from huaben.llm_fake import FakeLLM
from huaben.pipeline.chapter import generate_chapter
from huaben.pipeline.prompts import OUTLINE_SCHEMA, outline_messages, work_order
from huaben.planting import (HOOK_RULE, OPEN_TOTAL_LIMIT, PLANT_RULE, PLANT_SCHEMA, normalize_plant, plant_rule,
                             to_register)

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)
PLANT = {"content": "账本页脚有一行小字", "truth": "老道早就知道主角身世", "scale": "long"}


def test_normalize_plant_requires_content_and_truth():
    assert normalize_plant({"content": "a", "truth": "b", "scale": "长线"}) == {"content": "a", "truth": "b",
                                                                                "scale": "long", "key": ""}
    assert normalize_plant({"content": "a", "truth": ""}) is None
    assert normalize_plant(None) is None and normalize_plant("x") is None


def test_to_register_only_registers_the_planned_plant():
    reg, notes = to_register(None, 3, [{"content": "脚印"}])
    assert reg == [] and len(notes) == 1 and "计划外的悬念" in notes[0] and "脚印" in notes[0]
    reg, notes = to_register(PLANT, 3, [])
    assert len(reg) == 1 and reg[0]["payoff_plan"] == PLANT["truth"] and notes == []
    reg, notes = to_register(PLANT, OPEN_TOTAL_LIMIT + 1, [])
    assert reg == [] and any("超过上限" in n for n in notes)


def test_plant_rule_switches_at_the_limit():
    assert plant_rule(OPEN_TOTAL_LIMIT) == PLANT_RULE
    assert "必须为 null" in plant_rule(OPEN_TOTAL_LIMIT + 1)


def test_outline_schema_contains_the_plant_schema():
    assert PLANT_SCHEMA in OUTLINE_SCHEMA


def test_editor_is_told_to_use_existing_things_for_hooks(conn):
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, status="active")
    user = outline_messages(load_context(conn, bid))[1]["content"]
    assert HOOK_RULE in user and PLANT_RULE in user and "结尾留钩子;" not in user


def test_work_order_shows_plant_and_truth_or_says_none():
    o = {"title": "T", "outline": "事", "hook": "钩", "plant": PLANT, "characters": [], "foreshadows": [],
         "planned_reversals": []}
    w = work_order(5, o)
    assert "本章要埋的伏笔" in w and PLANT["content"] in w and PLANT["truth"] in w
    assert "本章不埋新伏笔" in work_order(5, {**o, "plant": None})


def _book(conn):
    bid = repo.create_book(conn, "诡仙")
    repo.create_volume(conn, bid, 1, goal="入门", status="active")
    repo.upsert_character(conn, bid, "沈照", core=True, location="山门")
    return bid


def _outline(plant_marker=...):
    d = {"title": "夜巡", "outline": "沈照夜里巡查。", "characters": ["沈照"], "foreshadows": [],
         "planned_reversals": [], "hook": "井里有人在敲"}
    if plant_marker is not ...:
        d["plant"] = plant_marker
    return json.dumps(d, ensure_ascii=False)


def _ledger(news):
    return json.dumps({"summary": "沈照夜巡听到井声。", "characters": [{"name": "沈照", "location": "井边"}],
                       "foreshadows_new": news, "foreshadows_update": [], "facts": [], "contradictions": []},
                      ensure_ascii=False)


def test_planned_plant_is_registered_with_its_truth(conn):
    book = _book(conn)
    two = [{"content": "脚印", "payoff_plan": "套话"}, {"content": "布条", "payoff_plan": "套话"}]
    generate_chapter(conn, FakeLLM([_outline(PLANT), "正文一。", _ledger(two)]), S, book)
    fs = repo.list_foreshadows(conn, book)
    assert len(fs) == 1 and fs[0]["content"] == PLANT["content"] and fs[0]["payoff_plan"] == PLANT["truth"]
    notes = [r[0] for r in conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE '%计划外的悬念%'")]
    assert len(notes) == 2 and all("脚印" in n or "布条" in n for n in notes)


def test_unplanned_extraction_is_not_registered(conn):
    book = _book(conn)
    generate_chapter(conn, FakeLLM([_outline(), "正文一。", _ledger([{"content": "神秘脚印"}])]), S, book)
    assert repo.list_foreshadows(conn, book) == []
