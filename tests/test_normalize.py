"""编辑输出的规整:常见变形就地修正,无法理解的显式 ParseError,下游永远只见确定类型。"""
import json

import pytest

from huaben import repo
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.pipeline.normalize import normalize_ledger, normalize_outline, to_bool
from huaben.pipeline.parsing import ParseError
from huaben.scheduler import top_up

PLAN = json.dumps({"goal": "g", "beats": ["a"], "plant": [], "resolve": [], "target_chapters": 30})
OUTLINE = json.dumps({"title": "T", "outline": "事", "characters": [], "foreshadows": [],
                      "planned_reversals": [], "hook": "钩"}, ensure_ascii=False)


def ledger(**kw):
    d = {"summary": "s", "characters": [], "foreshadows_new": [], "foreshadows_update": [], "facts": [],
         "contradictions": []}
    d.update(kw)
    return d


def test_common_deformations_are_normalized():
    out = normalize_ledger(ledger(
        characters=[{"name": " 沈照 ", "alive": "否", "core": "是", "knows": "井里有人", "location": 3}],
        foreshadows_new=["井里的声音"],
        foreshadows_update=[{"id": "#2", "status": "Resolved"}],
        facts=["后山有井", "", "后山有井", 42],
        contradictions=["名字写错了", {"what": "复活", "planned": "true"}],
    ))
    c = out["characters"][0]
    assert c == {"name": "沈照", "alive": False, "core": True, "knows": ["井里有人"], "location": "3"}
    assert out["foreshadows_new"] == [{"content": "井里的声音", "payoff_plan": "", "scale": "medium"}]  # 没写大小:按中线
    assert out["foreshadows_update"] == [{"id": 2, "status": "resolved"}]
    assert out["facts"] == ["后山有井", "42"]  # 去空、去重
    assert out["contradictions"] == [{"what": "名字写错了", "planned": False}, {"what": "复活", "planned": True}]


def test_absent_character_fields_stay_absent():
    """没给的字段不能补默认值,否则 merge_character 会把旧状态覆盖掉(例如把死人改回活人)。"""
    assert normalize_ledger(ledger(characters=[{"name": "老道"}]))["characters"] == [{"name": "老道"}]


@pytest.mark.parametrize("bad", [
    {"characters": [{"name": ""}]},
    {"characters": ["沈照"]},
    {"characters": [{"name": "x", "alive": "也许"}]},
    {"foreshadows_update": [3]},
    {"foreshadows_update": [{"id": "abc", "status": "resolved"}]},
    {"foreshadows_update": [{"id": 1, "status": "maybe"}]},
    {"foreshadows_new": [{"content": ""}]},
    {"facts": "不是列表"},
    {"summary": ""},
])
def test_uninterpretable_output_is_parse_error(bad):
    with pytest.raises(ParseError):
        normalize_ledger(ledger(**bad))


def test_unclear_planned_flag_counts_as_unplanned():
    out = normalize_ledger(ledger(contradictions=[{"what": "x", "planned": "maybe"}]))
    assert out["contradictions"][0]["planned"] is False  # 宁可误报重写,也不放过硬伤


def test_outline_normalization():
    o = normalize_outline({"title": " T ", "outline": "事", "characters": "沈照", "foreshadows": ["#3", 4],
                           "planned_reversals": None})
    assert o == {"title": "T", "outline": "事", "hook": "", "characters": ["沈照"], "foreshadows": [3, 4],
                 "planned_reversals": [], "payoff": "", "novelty": ""}
    with pytest.raises(ParseError):
        normalize_outline({"title": "", "outline": "x"})


def test_to_bool():
    assert to_bool("存活", "f") is True and to_bool("已死亡", "f") is False and to_bool(0, "f") is False
    with pytest.raises(ParseError):
        to_bool(2, "f")


@pytest.mark.parametrize("raw", [
    {"foreshadows_new": ["井里的声音"]},                  # 实测曾抛 TypeError
    {"characters": [{"name": "沈照", "alive": "否"}]},    # 实测曾抛 ValueError
])
def test_previously_crashing_outputs_now_accepted(conn, raw):
    bid = repo.create_book(conn, "x")
    repo.update_book(conn, bid, status="serializing")
    led = json.dumps(ledger(**raw), ensure_ascii=False)
    res = top_up(conn, FakeLLM([PLAN, OUTLINE, "正文", led]), Settings(openrouter_api_key="x", chapter_words=1, buffer_chapters=1,
                                                                    _env_file=None), bid)
    assert res.error == "" and res.generated == 1


def test_bad_ledger_retries_ledger_only_then_visible_failure(conn):
    """入账输出无法理解:先只重试入账(不扔正文);每稿两次都失败、写满三稿后显式失败并写进 gen_error。"""
    bid = repo.create_book(conn, "x")
    repo.update_book(conn, bid, status="serializing")
    bad = json.dumps(ledger(foreshadows_update=[3]))  # 实测曾抛 AttributeError 且 gen_error 为空
    good = json.dumps(ledger())
    llm = FakeLLM([PLAN, OUTLINE, "正文", bad, good])
    res = top_up(conn, llm, Settings(openrouter_api_key="x", chapter_words=1, buffer_chapters=1, _env_file=None), bid)
    assert res.generated == 1 and repo.get_chapter(conn, bid, 1)["attempts"] == 1  # 同一稿正文入账成功
    bid2 = repo.create_book(conn, "y")
    repo.update_book(conn, bid2, status="serializing")
    llm2 = FakeLLM([PLAN, OUTLINE] + ["正文", bad, bad] * 3)
    res2 = top_up(conn, llm2, Settings(openrouter_api_key="x", chapter_words=1, buffer_chapters=1, _env_file=None), bid2)
    assert res2.error and repo.get_book(conn, bid2)["gen_error"]


def test_real_run_ledger_shapes_are_tolerated():
    """2026-10-02 生产环境第 1 章:'planted' 状态、单个对象不套列表——两次都让整份入账作废、整章重写。"""
    d = normalize_ledger(ledger(foreshadows_update=[{"id": 1, "status": "planted"}, {"id": 2, "status": "已回收"},
                                                    {"id": 3, "status": "推进中"}]))
    assert d["foreshadows_update"] == [{"id": 2, "status": "resolved"}, {"id": 3, "status": "progressing"}]
    one = normalize_ledger(ledger(foreshadows_update={"id": 4, "status": "resolved"}, characters={"name": "周小满"}))
    assert one["foreshadows_update"] == [{"id": 4, "status": "resolved"}] and one["characters"][0]["name"] == "周小满"
