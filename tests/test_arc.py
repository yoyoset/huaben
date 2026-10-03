"""一卷 = 一段征战(2026-10-03 用户:吸引人的连载就是一段段征战,只是呈现方式多种多样)。"""
import json

from huaben import repo
from huaben.arc import arc_pacing, normalize_arc, past_modes, render_arc
from huaben.context import load_context
from huaben.pipeline.parsing import parse_volume_plan
from huaben.pipeline.prompts import outline_messages
from huaben.pipeline.volume_prompts import plan_messages

ARC = {"antagonist": "账房总管", "motive": "他觉得寒门上位会毁了规矩", "edge": "掌握全部旧账", "stakes": "父亲的名声",
       "mode": "智斗骗局", "low_point_beat": 3, "low_point": "假户籍被当众揭穿", "cost": "失去唯一的证人",
       "change": "主角从躲着走变成主动设局", "thread": "残片主人露出一角", "world": "从县城推到州府"}


def test_arc_needs_the_core_items_and_clamps_low_point():
    assert normalize_arc(ARC, 4)["low_point_beat"] == 3
    assert normalize_arc({**ARC, "low_point_beat": 99}, 4)["low_point_beat"] == 4
    assert normalize_arc({**ARC, "low_point_beat": "?"}, 6)["low_point_beat"] == 4   # 没给:放在三分之二处
    assert normalize_arc({**ARC, "motive": ""}, 4) is None                          # 对手没有自己的道理:不算规划好了
    assert normalize_arc("不是对象", 4) is None
    assert normalize_arc({**ARC, "world": ""}, 4)["world"] == ""  # world 可空:老规划没有它也能用


def test_world_ladder_only_goes_up():
    """2026-10-03 用户:要写出《海贼王》《火影》《死神》那种故事——卷卷把世界的尺度往上推(东海→伟大航路)。"""
    from huaben.arc import past_worlds, world_ladder_rule
    vols = [{"idx": 1, "arc": {"world": "县城"}}, {"idx": 2, "arc": {"world": "州府"}}, {"idx": 3, "arc": {}}]
    assert past_worlds(vols) == ["第1卷:县城", "第2卷:州府"]
    assert world_ladder_rule([]) == ""                                  # 第一卷无从比较
    rule = world_ladder_rule(past_worlds(vols))
    assert "只升不降" in rule and "县城" in rule and "州府" in rule
    assert normalize_arc(ARC, 4)["world"] == "从县城推到州府"
    assert "世界坐标:从县城推到州府" in render_arc(normalize_arc(ARC, 4))


def test_pacing_follows_the_arc_shape():
    arc = normalize_arc(ARC, 4)
    assert "对手要一步步占上风" in arc_pacing(arc, 2, 10)
    assert "逼到最低处" in arc_pacing(arc, 3, 8)
    assert "不是对手突然犯蠢" in arc_pacing(arc, 4, 3)
    assert "胜利的代价必须在本章落地" in arc_pacing(arc, 4, 0)
    assert arc_pacing(None, 2, 5) == ""


def test_plan_asks_for_an_arc_and_a_new_mode():
    vols = [{"idx": 1, "arc": {"mode": "智斗骗局"}}, {"idx": 2, "arc": {}}]
    assert past_modes(vols) == ["第1卷:智斗骗局"]
    plan = {"goal": "g", "beats": ["起", "承", "转", "合"], "plant": [], "resolve": [], "target_chapters": 20, "arc": ARC}
    parsed = parse_volume_plan(json.dumps(plan, ensure_ascii=False))
    assert parsed["arc"]["antagonist"] == "账房总管"
    assert parse_volume_plan(json.dumps({**plan, "arc": {}}, ensure_ascii=False))["arc"] is None  # 缺了不打回整份规划


def test_editor_and_writer_see_the_arc(conn):
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, goal="入门", beats=["起", "承", "转", "合"], status="active",
                       target_chapters=8, arc=normalize_arc(ARC, 4))
    ctx = load_context(conn, bid)
    user = outline_messages(ctx)[1]["content"]
    assert "本卷是一段征战" in user and "他的道理:他觉得寒门上位会毁了规矩" in user
    assert "对手要一步步占上风" in user  # 第 1 章,谷底在第 3 个节拍之前
    assert "本卷换一种打法" in plan_messages(ctx, 2, used_modes=["第1卷:智斗骗局"])[1]["content"]
    assert "只升不降" in plan_messages(ctx, 2, used_worlds=["第1卷:县城"])[1]["content"]
    assert render_arc(None) == ""


def test_fill_arc_upgrades_an_existing_volume(tmp_path):
    from huaben.llm_fake import FakeLLM
    from test_voice_api import setup
    s, conn, (a, b), c = setup(tmp_path)
    c.app.state.llm = FakeLLM([json.dumps(ARC, ensure_ascii=False)])
    c.app.state.llm_injected = True
    r = c.post(f"/api/books/{a}/volume/arc").json()
    assert r["antagonist"] == "账房总管" and repo.active_volume(conn, a)["arc"]["stakes"] == "父亲的名声"
