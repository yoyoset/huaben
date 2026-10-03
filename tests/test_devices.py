"""推动情节的手段别一用再用(2026-10-03 实测:《算尽仙朝》10 章章章"残片发烫",《杂役仙尊》14 章里 12 章靠枕下纸条)。"""
import json

from huaben import repo
from huaben.context import load_context
from huaben.devices import avoid_rule, from_rows, normalize_devices, overused
from huaben.pipeline.ledger_apply import apply_ledger
from huaben.pipeline.normalize import normalize_ledger
from huaben.pipeline.prompts import ledger_messages, outline_messages, write_messages

OUTLINE = {"title": "T", "outline": "事", "characters": [], "foreshadows": [], "planned_reversals": [], "hook": "钩"}


def test_normalize_is_forgiving():
    assert normalize_devices(["残片浮现字迹", " 残片浮现字迹 ", "", "枕下纸条"]) == ["残片浮现字迹", "枕下纸条"]
    assert normalize_devices("密信") == ["密信"] and normalize_devices(None) == [] and normalize_devices(42) == []
    assert normalize_devices(["一个特别特别特别长的手段名字啊啊"])[0] == "一个特别特别特别长的手段"  # 截到 12 字


def test_overuse_needs_two_of_the_recent_chapters():
    recent = [["残片浮现字迹", "偷听"], ["残片浮现字迹"], ["枕下纸条"]]
    assert overused(recent) == [("残片浮现字迹", 2)]
    assert "残片浮现字迹(2/3 章)" in avoid_rule(recent)
    assert avoid_rule([["偷听"], ["密信"], []]) == ""
    assert from_rows([{"devices": '["密信"]'}, {"devices": "坏"}, {}]) == [["密信"], [], []]


def test_ledger_records_devices_and_next_chapter_is_told_to_avoid(conn):
    bid = repo.create_book(conn, "x")
    vid = repo.create_volume(conn, bid, 1, status="active")
    for i in (1, 2, 3):
        cid = repo.create_chapter(conn, bid, vid, i, title=f"T{i}")
        ledger = normalize_ledger({"summary": "s", "characters": [], "foreshadows_new": [], "foreshadows_update": [],
                                   "facts": [], "contradictions": [],
                                   "devices": ["残片浮现字迹"] if i != 2 else ["偷听"]})
        repo.update_chapter(conn, cid, body="b")
        apply_ledger(conn, bid, cid, i, ledger)
    assert json.loads(repo.get_chapter(conn, bid, 1)["devices"]) == ["残片浮现字迹"]
    ctx = load_context(conn, bid)
    assert "残片浮现字迹(2/3 章)" in outline_messages(ctx)[1]["content"]
    assert "残片浮现字迹(2/3 章)" in write_messages(ctx, OUTLINE, 1000)[1]["content"]
    assert "【最近用过的手段】偷听、残片浮现字迹" in ledger_messages(ctx, OUTLINE, "正文")[1]["content"]
