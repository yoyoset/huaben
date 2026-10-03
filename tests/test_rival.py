"""长期对手(宿敌,路线 64):会跟主角一起成长的那种对手。

2026-10-03 用户:要能写出《海贼王》《火影》《死神》那种故事——那三部的上头很大程度靠长期对手
(索隆/鹰眼、鸣人/佐助、一护/白哉),不是一次性 boss,而是隔几卷回来一次且每次更强。
"""
import json

from huaben import repo
from huaben.context import load_context
from huaben.pipeline.volume_prompts import plan_messages
from huaben.render import render_bible
from huaben.rival import advance_rule, advanced_by, from_bible, render


BIBLE = {"characters": [
    {"name": "沈砚之", "role": "主角", "traits": "腹黑"},
    {"name": "裴无咎", "role": "世家天才", "traits": "高傲", "rival": True},
    {"name": "玄尘子", "role": "主考长老", "traits": "老狐狸"},
]}


def test_from_bible_picks_only_marked_rivals():
    assert from_bible(BIBLE) == ["裴无咎"]
    assert from_bible({"characters": [{"name": "A"}]}) == []
    assert from_bible(None) == []


def test_render_and_advance_rule():
    assert "长期对手(宿敌)" in render(["裴无咎"]) and "裴无咎" in render(["裴无咎"])
    assert render([]) == ""
    assert advance_rule([], []) == ""
    rule = advance_rule(["裴无咎"], ["第1卷:裴无咎"])
    assert "至少一个长期对手有实质变化" in rule and "第1卷:裴无咎" in rule


def test_advanced_by_matches_antagonist_text():
    vols = [{"idx": 1, "arc": {"antagonist": "裴无咎与世家泄题网"}}, {"idx": 2, "arc": {"antagonist": "一位神秘前辈"}}]
    assert advanced_by(vols, ["裴无咎"]) == ["第1卷:裴无咎"]
    assert advanced_by(vols, ["不存在的人"]) == []


def test_render_bible_marks_rival():
    out = render_bible(BIBLE)
    assert "裴无咎:世家天才 高傲(长期对手)" in out
    assert "玄尘子:主考长老 老狐狸" in out and "玄尘子:主考长老 老狐狸(长期对手)" not in out


def test_volume_plan_prompt_asks_to_advance_a_rival(conn):
    bid = repo.create_book(conn, "书")
    repo.save_bible(conn, bid, characters=BIBLE["characters"])
    repo.create_volume(conn, bid, 1, status="active")
    ctx = load_context(conn, bid)
    user = plan_messages(ctx, 2, used_rivals=["第1卷:裴无咎"])[1]["content"]
    assert "长期对手" in user and "至少一个长期对手有实质变化" in user
    # 开书没标宿敌的书:不加这条,不强行编造
    bid2 = repo.create_book(conn, "无宿敌")
    repo.save_bible(conn, bid2, characters=[{"name": "甲", "role": "主角", "traits": "x"}])
    repo.create_volume(conn, bid2, 1, status="active")
    assert "长期对手" not in plan_messages(load_context(conn, bid2), 2)[1]["content"]
