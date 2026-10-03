"""每个节拍分几章:locate/normalize/beat_line 纯函数,以及预算进卷规划与写章提示词。"""
import json

from huaben import repo
from huaben.beat_budget import BUDGET_RULE, beat_line, locate, normalize_budget
from huaben.context import StoryContext, load_context
from huaben.pipeline.parsing import parse_volume_plan
from huaben.pipeline.prompts import outline_messages, write_messages
from huaben.pipeline.volume_prompts import plan_messages

OUTLINE = {"title": "T", "outline": "事", "characters": [], "foreshadows": [], "planned_reversals": [], "hook": "钩"}


def test_locate_maps_done_to_beat_position():
    assert locate([1, 3, 2], 0) == (1, 1, 1)
    assert locate([1, 3, 2], 1) == (2, 1, 3)
    assert locate([1, 3, 2], 3) == (2, 3, 3)
    assert locate([1, 3, 2], 4) == (3, 1, 2)
    assert locate([1, 3, 2], 6) == (3, 2, 2)   # 写超了:停在最后一个节拍的最后一章
    assert locate([0, 2, 3], 0) == (2, 1, 2)   # 跳过预算为 0 的节拍


def test_normalize_budget_rejects_bad_shape_and_clamps():
    assert normalize_budget([1, 3, 2], 3) == [1, 3, 2]
    assert normalize_budget([1, 3], 3) is None
    assert normalize_budget([1, "3", 2], 3) is None
    assert normalize_budget([0, 20, 2], 3) == [1, 8, 2]
    assert normalize_budget(None, 3) is None


def test_beat_line_speaks_differently_for_transition_climax_and_last():
    assert "只给 1 章" in beat_line(["a", "b"], 1, 1, 1) and "「b」" in beat_line(["a", "b"], 1, 1, 1)
    assert "最后一章" in beat_line(["a", "b"], 2, 3, 3) and "本卷的收尾" in beat_line(["a", "b"], 2, 3, 3)
    assert "重头戏" in beat_line(["a", "b"], 1, 1, 3) and "第 1 章" in beat_line(["a", "b"], 1, 1, 3)
    assert "大约应推进" in beat_line(["a", "b"], 1, 0, 0)


def _plan(**kw):
    d = {"goal": "g", "beats": ["a", "b", "c"], "plant": [], "resolve": [], "target_chapters": 99, "arc": {}}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


def test_parse_volume_plan_sets_target_to_the_budget_sum():
    d = parse_volume_plan(_plan(beat_chapters=[1, 3, 2]))
    assert d["beat_chapters"] == [1, 3, 2] and d["target_chapters"] == 6


def test_parse_volume_plan_falls_back_when_budget_length_mismatched():
    d = parse_volume_plan(_plan(beat_chapters=[1, 3]))  # 长度对不上:不报错,退回平均算法
    assert d["beat_chapters"] is None and d["target_chapters"] == 99


def test_plan_prompt_asks_for_a_per_beat_budget(conn):
    ctx = load_context(conn, repo.create_book(conn, "x"))
    assert BUDGET_RULE in plan_messages(ctx, 1)[1]["content"]


def _ctx(done: int, beats, budget, target: int = 10) -> StoryContext:
    vol = {"id": 1, "idx": 2, "goal": "g", "beats": list(beats), "plant": [], "resolve": [],
           "target_chapters": target, "beat_chapters": list(budget)}
    return StoryContext(book={"synopsis": ""}, bible={}, volume=vol, past_volume_summaries=[],
                        volume_chapter_summaries=[], recent=[], characters=[], foreshadows=[], facts=[],
                        next_idx=11 + done, volume_done=done)


def test_budgeted_volume_shows_the_same_line_to_editor_and_writer():
    beats, budget = ["镇上算账", "考场策论", "外门杂役"], [1, 3, 2]
    line = beat_line(beats, *locate(budget, 0))  # done=0 → 第 1 个节拍、只给 1 章
    assert "只给 1 章" in line
    c = _ctx(0, beats, budget, target=sum(budget))
    assert line in outline_messages(c)[-1]["content"]
    assert line in write_messages(c, OUTLINE, 1000)[-1]["content"]


def test_volume_without_budget_keeps_the_average_wording():
    c = _ctx(0, ["起", "承", "转", "合", "收"], [], target=10)
    assert "大约应推进" in write_messages(c, OUTLINE, 1000)[-1]["content"]
