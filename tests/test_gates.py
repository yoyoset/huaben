"""T030 打回理由分级:致命问题哪一档、哪一稿都拦;缺原话、结尾、碎句这类"重"问题,
只在中/松档的最后一稿放行(留痕不打回)。矛盾仍按 T029 分档,与本卡无关。
"""
import json

import pytest

from huaben import repo
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.pipeline.chapter import ChapterFailed, generate_chapter

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)


def _book(conn):
    bid = repo.create_book(conn, "诡仙")
    repo.create_volume(conn, bid, 1, goal="入门", status="active")
    repo.upsert_character(conn, bid, "沈照", core=True)
    return bid


def _outline(**kw):
    d = {"title": "立誓", "outline": "沈照立誓。", "characters": ["沈照"], "foreshadows": [],
         "planned_reversals": [], "hook": "灯灭了", "lines": ["我不跑了。"]}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


def _ledger(contradictions=None):
    return json.dumps({"summary": "沈照立誓。", "characters": [], "foreshadows_new": [], "foreshadows_update": [],
                       "facts": [], "contradictions": contradictions or []}, ensure_ascii=False)


def test_medium_grip_last_draft_lets_missing_line_through(conn):
    """中档:三稿都缺原话,第三稿(末稿)留痕放行,不再整章失败。"""
    bid = _book(conn)
    llm = FakeLLM([_outline(grip="中"), "一稿。", "二稿。", "三稿。", _ledger()])
    ch = generate_chapter(conn, llm, S, bid)
    assert ch["status"] == "accepted" and ch["attempts"] == 3
    notes = [r[0] for r in conn.execute("SELECT note FROM pipeline_runs ORDER BY id")]
    assert sum(n.startswith("draft:") for n in notes) == 2   # 前两稿打回
    assert any(n.startswith("末稿放行(未打回)") for n in notes)


def test_tight_grip_missing_line_still_fails(conn):
    """紧档(含没填):缺原话永不放行,三稿后照旧失败。"""
    bid = _book(conn)
    with pytest.raises(ChapterFailed):
        generate_chapter(conn, FakeLLM([_outline(grip="紧"), "一稿。", "二稿。", "三稿。"]), S, bid)


def test_loose_grip_size_failure_is_fatal_on_every_draft(conn):
    """致命问题(篇幅不足)不因松档末稿放行而通过。"""
    bid = _book(conn)
    with pytest.raises(ChapterFailed):
        generate_chapter(conn, FakeLLM([_outline(grip="松", lines=[]), "", "", ""]), S, bid)


def test_loose_grip_must_contradiction_fails_all_drafts(conn):
    """松档:以"不能错:"开头的矛盾每一稿都打回,三稿后失败。"""
    bid = _book(conn)
    bad = _ledger([{"what": "不能错:厉九出手了", "planned": False}])
    llm = FakeLLM([_outline(grip="松", lines=[]), "一稿。", bad, "二稿。", bad, "三稿。", bad])
    with pytest.raises(ChapterFailed):
        generate_chapter(conn, llm, S, bid)
