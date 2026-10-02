"""伏笔的预算与对账:prompt 里有上限且优先级正确;卷计划按编号指向伏笔;封卷对账、未收的转交下一卷。"""
import json

import pytest

from huaben import repo
from huaben.config import Settings
from huaben.context import load_context, select_foreshadows
from huaben.llm_fake import FakeLLM
from huaben.pipeline.errors import ChapterFailed
from huaben.pipeline.parsing import ParseError, parse_volume_plan
from huaben.pipeline.volume import plan_volume, seal_volume
from huaben.render import render_memory

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)
SEAL = json.dumps({"volume_summary": "卷摘要", "synopsis": "梗概"}, ensure_ascii=False)


def plan(**kw):
    d = {"goal": "g", "beats": ["a"], "plant": [], "resolve": [], "target_chapters": 5}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


def fs(i, ch):
    return {"id": i, "planted_ch": ch, "content": f"伏笔{i}", "payoff_plan": "", "status": "planted"}


def test_select_caps_and_prioritises():
    open_fs = [fs(i, i) for i in range(1, 21)]
    shown, hidden = select_foreshadows(open_fs, priority_ids={19}, limit=5)
    assert [f["id"] for f in shown] == [1, 2, 3, 4, 19]  # 优先级先占位,其余按最早埋下;展示时按埋下先后
    assert hidden == 15


def test_render_reports_hidden_count(conn):
    bid = repo.create_book(conn, "x")
    for i in range(1, 16):
        repo.add_foreshadow(conn, bid, i, f"伏笔{i}")
    out = render_memory(load_context(conn, bid))
    assert "#1 [中线] 第1章埋" in out and "#15 " not in out and "另有 3 条较新的未回收伏笔" in out


@pytest.mark.parametrize("raw,ids", [([3, "#4", "#5 玉佩发烫", 3], [3, 4, 5]), ([], [])])
def test_plan_resolve_takes_ids(raw, ids):
    assert parse_volume_plan(plan(resolve=raw))["resolve"] == ids


def test_plan_resolve_rejects_free_text():
    with pytest.raises(ParseError):
        parse_volume_plan(plan(resolve=["玉佩的秘密"]))


def test_plan_drops_unknown_or_resolved_ids_and_logs(conn):
    bid = repo.create_book(conn, "x")
    a = repo.add_foreshadow(conn, bid, 1, "玉佩")
    b = repo.add_foreshadow(conn, bid, 1, "井声")
    repo.update_foreshadow(conn, b, status="resolved", resolved_ch=2)
    v = plan_volume(conn, FakeLLM([plan(resolve=[a, b, 99])]), S, bid)
    assert v["resolve"] == [a]
    note = conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE '%无效的伏笔编号%'").fetchone()[0]
    assert str(b) in note and "99" in note


def test_seal_reconciles_and_next_plan_carries_missed(conn):
    bid = repo.create_book(conn, "x")
    a = repo.add_foreshadow(conn, bid, 1, "玉佩")
    b = repo.add_foreshadow(conn, bid, 1, "井声")
    v = plan_volume(conn, FakeLLM([plan(resolve=[a, b])]), S, bid)
    for i in range(1, 6):
        cid = repo.create_chapter(conn, bid, v["id"], i)
        repo.update_chapter(conn, cid, status="accepted", summary="s")
    repo.update_foreshadow(conn, a, status="resolved", resolved_ch=4)
    seal_volume(conn, FakeLLM([SEAL]), S, bid, v)
    note = conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE '%计划回收未完成%'").fetchone()[0]
    assert f"[{b}]" in note
    llm = FakeLLM([plan()])
    plan_volume(conn, llm, S, bid)
    assert f"上一卷计划回收却没有收的:#{b}" in llm.calls[0][-1]["content"]


def test_backlog_warning_when_too_many_open(conn):
    bid = repo.create_book(conn, "x")
    for i in range(1, 11):
        repo.add_foreshadow(conn, bid, i, f"伏笔{i}")
    llm = FakeLLM([plan()])
    plan_volume(conn, llm, S, bid)
    assert "未回收伏笔已积压 10 条" in llm.calls[0][-1]["content"]


def test_resolve_targets_shown_with_content(conn):
    bid = repo.create_book(conn, "x")
    a = repo.add_foreshadow(conn, bid, 1, "玉佩")
    plan_volume(conn, FakeLLM([plan(resolve=[a])]), S, bid)
    assert f"本卷要收的伏笔:#{a} 玉佩" in render_memory(load_context(conn, bid))


def test_invalid_plan_twice_is_failure(conn):
    bid = repo.create_book(conn, "x")
    with pytest.raises(ChapterFailed):
        plan_volume(conn, FakeLLM([plan(resolve=["没有编号"])] * 2), S, bid)
