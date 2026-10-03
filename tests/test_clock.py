"""场景时间(T006):章纲多一栏 when,并给编辑/作者一条作息常识。"""
import json

from huaben import repo
from huaben.clock import REALISM_RULE, WHEN_SCHEMA, recent_when
from huaben.context import load_context
from huaben.pipeline.normalize import normalize_outline
from huaben.pipeline.prompts import OUTLINE_SCHEMA, outline_messages, work_order, write_messages

OUTLINE = {"title": "T", "outline": "事", "characters": [], "foreshadows": [], "planned_reversals": [], "hook": "钩"}


def test_recent_when_skips_old_and_bad_rows():
    recent = [{"idx": 1, "outline": json.dumps({"when": "清晨"}, ensure_ascii=False)},
              {"idx": 2, "outline": "{}"},
              {"idx": 3, "outline": "不是 JSON"},
              {"idx": 4, "outline": json.dumps({"when": "第二天夜里"}, ensure_ascii=False)}]
    out = recent_when(recent)
    assert "- 第1章:清晨" in out and "- 第4章:第二天夜里" in out and "接得上" in out
    assert "- 第2章" not in out and "- 第3章" not in out
    assert recent_when([{"idx": 1, "outline": "{}"}]) == ""
    assert recent_when([]) == ""


def test_normalize_outline_keeps_optional_when():
    base = {"title": "T", "outline": "事"}
    assert normalize_outline({**base, "when": "第二天"})["when"] == "第二天"
    assert normalize_outline(base)["when"] == ""  # 缺它不打回章纲


def test_outline_schema_carries_the_when_line():
    assert WHEN_SCHEMA in OUTLINE_SCHEMA


def _book_with_recent(conn, whens):
    bid = repo.create_book(conn, "x")
    vid = repo.create_volume(conn, bid, 1, status="active")
    for i, when in enumerate(whens, 1):
        outline = json.dumps({"hook": "钩", "when": when}, ensure_ascii=False)
        cid = repo.create_chapter(conn, bid, vid, i, title=f"T{i}", outline=outline)
        repo.update_chapter(conn, cid, body="b", summary="s", status="accepted")
    return bid


def test_editor_sees_recent_times_and_the_realism_rule(conn):
    bid = _book_with_recent(conn, ["清晨", "", "第二天夜里"])
    user = outline_messages(load_context(conn, bid))[1]["content"]
    assert REALISM_RULE in user
    section = user.split("最近几章的时间")[1].split("本章的时间要和它们接得上")[0]
    assert "- 第1章:清晨" in section and "- 第3章:第二天夜里" in section and "- 第2章" not in section


def test_work_order_shows_when_only_if_present():
    assert "本章时间:第二天上午" in work_order(3, {**OUTLINE, "when": "第二天上午"})
    assert "本章时间" not in work_order(3, OUTLINE)  # 旧章纲没有这一栏不能报错


def test_writer_gets_realism_rule_instead_of_bond_rule(conn):
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, status="active")
    user = write_messages(load_context(conn, bid), OUTLINE, 1000)[1]["content"]
    assert REALISM_RULE in user and "伙伴关系要一部部攒起来" not in user
    hard = user.split("硬性要求:")[1]
    pos = [hard.index(f"{i}.") for i in range(1, 10)]
    assert pos == sorted(pos) and "\n\n" not in hard  # 编号仍连续、无空行(T005)
