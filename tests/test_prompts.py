"""prompt 组装:编辑的计划必须完整交到作者/核对者手上。"""
import pytest

from huaben import repo
from huaben.context import load_context
from huaben.pipeline.prompts import ledger_messages, outline_scope, work_order, write_messages


def outline(**kw):
    d = {"title": "井底", "outline": "沈照下井", "characters": ["沈照"], "foreshadows": [],
         "planned_reversals": [], "hook": "灯灭了"}
    d.update(kw)
    return d


@pytest.fixture
def ctx(conn):
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, goal="g", status="active")
    repo.upsert_character(conn, bid, "沈照", core=True)
    return load_context(conn, bid)


def test_work_order_without_reversal():
    w = work_order(3, outline())
    assert "第 3 章《井底》" in w and "沈照下井" in w and "结尾钩子:灯灭了" in w
    assert "反转" not in w


def test_planned_reversal_reaches_the_writer(ctx):
    o = outline(planned_reversals=["老道没死,是假死脱身"])
    user = write_messages(ctx, o, 2500)[-1]["content"]
    assert "老道没死,是假死脱身" in user                    # 计划交到了作者手上
    assert "除工单列出的有意反转外,严格遵守账本" in user      # 硬约束给反转留了口子,指令不再自相矛盾


def test_no_reversal_keeps_strict_rule(ctx):
    user = write_messages(ctx, outline(), 2500)[-1]["content"]
    assert "2. 严格遵守账本里的人物现状与世界事实" in user and "有意反转" not in user


def test_ledger_check_still_sees_reversals(ctx):
    user = ledger_messages(ctx, outline(planned_reversals=["假死"]), "正文")[-1]["content"]
    assert "假死" in user


def test_outline_scope_separates_words():
    assert outline_scope(outline(outline="井", characters=["阿蘅", "老道"])) == "井 阿蘅 老道"
