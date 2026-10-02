import json

import pytest

from huaben import repo
from huaben.config import Settings
from huaben.llm import LLMError, LLMResult
from huaben.llm_fake import FakeLLM
from huaben.pipeline.chapter import ChapterFailed, NoActiveVolume, generate_chapter
from huaben.pipeline.ledger_apply import merge_character

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)

OUTLINE = json.dumps({"title": "夜巡", "outline": "沈照夜里巡查,发现井边有异响。", "characters": ["沈照"],
                      "foreshadows": [], "planned_reversals": [], "hook": "井里有人在敲"}, ensure_ascii=False)


def ledger(contradictions=None, **kw):
    d = {"summary": "沈照夜巡听到井声。", "characters": [{"name": "沈照", "location": "井边"}],
         "foreshadows_new": [{"content": "井里的敲击声", "payoff_plan": "卷末"}],
         "foreshadows_update": [], "facts": ["井在后山"], "contradictions": contradictions or []}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


@pytest.fixture
def book(conn):
    bid = repo.create_book(conn, "诡仙")
    repo.create_volume(conn, bid, 1, goal="入门", status="active")
    repo.upsert_character(conn, bid, "沈照", core=True, location="山门")
    return bid


def test_happy_path_accepts_and_posts_ledger(conn, book):
    llm = FakeLLM([OUTLINE, "正文一。", ledger()])
    ch = generate_chapter(conn, llm, S, book)
    assert ch["status"] == "accepted" and ch["idx"] == 1 and ch["body"] == "正文一。"
    assert ch["summary"] == "沈照夜巡听到井声。" and ch["title"] == "夜巡"
    c = repo.list_characters(conn, book)[0]
    assert c["location"] == "井边" and c["core"] is True  # 未返回的 core 字段被保留
    assert [f["content"] for f in repo.list_foreshadows(conn, book)] == ["井里的敲击声"]
    assert repo.list_facts(conn, book)[0]["fact"] == "井在后山"
    assert repo.cost_summary(conn, book)["chapters"] == 1  # 三步都记了账


def test_unplanned_contradiction_rewrites_with_feedback(conn, book):
    bad = ledger([{"what": "老道已死却开口说话", "planned": False}])
    llm = FakeLLM([OUTLINE, "稿一", bad, "稿二", ledger()])
    ch = generate_chapter(conn, llm, S, book)
    assert ch["body"] == "稿二" and ch["attempts"] == 2
    rewrite_prompt = llm.calls[3][-1]["content"]  # 第二次 write 的 user 消息
    assert "老道已死却开口说话" in rewrite_prompt
    assert len(repo.list_facts(conn, book)) == 1  # 只入账一次
    assert len(repo.list_foreshadows(conn, book)) == 1  # 被打回那稿没有入账


def test_planned_reversal_is_not_a_contradiction(conn, book):
    ok = ledger([{"what": "他居然没死", "planned": True}])
    ch = generate_chapter(conn, FakeLLM([OUTLINE, "稿", ok]), S, book)
    assert ch["status"] == "accepted" and ch["attempts"] == 1


def test_truncated_draft_is_retried(conn, book):
    cut = LLMResult(text="写到一半", truncated=True)
    ch = generate_chapter(conn, FakeLLM([OUTLINE, cut, "完整稿", ledger()]), S, book)
    assert ch["body"] == "完整稿"


def test_exhausted_attempts_fail_loudly_and_leave_no_gap(conn, book):
    bad = ledger([{"what": "冲突", "planned": False}])
    llm = FakeLLM([OUTLINE] + ["稿", bad] * 3)
    with pytest.raises(ChapterFailed):
        generate_chapter(conn, llm, S, book)
    assert repo.accepted_chapters(conn, book) == []
    assert repo.get_chapter(conn, book, 1)["status"] == "failed"
    assert repo.list_foreshadows(conn, book) == []  # 失败章不污染账本
    # 重试:半成品被清掉,仍从第 1 章开始,序号无空洞
    ch = generate_chapter(conn, FakeLLM([OUTLINE, "稿", ledger()]), S, book)
    assert ch["idx"] == 1 and ch["status"] == "accepted"


def test_outline_parse_failure_retries_once_then_fails(conn, book):
    with pytest.raises(ChapterFailed, match="章纲"):
        generate_chapter(conn, FakeLLM(["不是json", "还是不是"]), S, book)
    ch = generate_chapter(conn, FakeLLM(["```json\n" + OUTLINE + "\n```", "稿", ledger()]), S, book)
    assert ch["status"] == "accepted"  # 围栏包裹的 JSON 能解析


def test_llm_error_propagates_and_is_logged(conn, book):
    with pytest.raises(LLMError):
        generate_chapter(conn, FakeLLM([LLMError("HTTP 401")]), S, book)
    n = conn.execute("SELECT COUNT(*) FROM pipeline_runs WHERE ok=0").fetchone()[0]
    assert n == 1


def test_no_active_volume(conn):
    bid = repo.create_book(conn, "x")
    with pytest.raises(NoActiveVolume):
        generate_chapter(conn, FakeLLM([]), S, bid)


def test_second_chapter_sees_first_in_prompt(conn, book):
    generate_chapter(conn, FakeLLM([OUTLINE, "第一章原文XYZ", ledger()]), S, book)
    llm = FakeLLM([OUTLINE, "稿二", ledger()])
    ch = generate_chapter(conn, llm, S, book)
    assert ch["idx"] == 2
    assert "第一章原文XYZ" in llm.calls[1][-1]["content"]  # 写第 2 章时带上了第 1 章原文


def test_foreshadow_updates_and_unknown_ids(conn, book):
    fid = repo.add_foreshadow(conn, book, 0, "旧伏笔")
    led = ledger(foreshadows_update=[{"id": fid, "status": "resolved"}, {"id": 999, "status": "resolved"}])
    generate_chapter(conn, FakeLLM([OUTLINE, "稿", led]), S, book)
    f = [x for x in repo.list_foreshadows(conn, book) if x["id"] == fid][0]
    assert f["status"] == "resolved" and f["resolved_ch"] == 1
    warn = conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE '%999%'").fetchone()
    assert warn is not None


def test_merge_character_keeps_old_fields():
    old = {"alive": True, "location": "A", "abilities": "剑", "relations": "", "knows": ["x"], "core": True}
    m = merge_character(old, {"location": "B"})
    assert m["location"] == "B" and m["abilities"] == "剑" and m["core"] is True and m["knows"] == ["x"]


def test_resolved_foreshadow_cannot_be_reopened(conn, book):
    """实测曾出现:已回收的伏笔被入账改回 progressing,resolved_ch 清空、回收记录丢失。"""
    from huaben.pipeline.ledger_apply import apply_ledger
    vid = repo.active_volume(conn, book)["id"]
    fid = repo.add_foreshadow(conn, book, 1, "玉佩")
    repo.update_foreshadow(conn, fid, status="resolved", resolved_ch=3)
    cid = repo.create_chapter(conn, book, vid, 4)
    warns = apply_ledger(conn, book, cid, 4, {"summary": "s", "characters": [], "foreshadows_new": [], "facts": [],
                                               "foreshadows_update": [{"id": fid, "status": "progressing"}],
                                               "contradictions": []})
    f = repo.list_foreshadows(conn, book)[0]
    assert f["status"] == "resolved" and f["resolved_ch"] == 3
    assert any("already resolved" in w for w in warns)


def test_foreshadow_can_move_forward(conn, book):
    from huaben.pipeline.ledger_apply import apply_ledger
    vid = repo.active_volume(conn, book)["id"]
    fid = repo.add_foreshadow(conn, book, 1, "玉佩")
    for idx, status in ((2, "progressing"), (3, "progressing"), (4, "resolved")):
        cid = repo.create_chapter(conn, book, vid, idx)
        apply_ledger(conn, book, cid, idx, {"summary": "s", "characters": [], "foreshadows_new": [], "facts": [],
                                            "foreshadows_update": [{"id": fid, "status": status}], "contradictions": []})
    f = repo.list_foreshadows(conn, book)[0]
    assert f["status"] == "resolved" and f["resolved_ch"] == 4
