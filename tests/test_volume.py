import json

import pytest

from huaben import repo
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.pipeline.errors import ChapterFailed
from huaben.pipeline.volume import ensure_active_volume, plan_volume, seal_volume

S = Settings(openrouter_api_key="x", _env_file=None)


def plan_json(**kw):
    d = {"goal": "入门", "beats": ["拜师", "试炼"], "plant": ["玉佩"], "resolve": [], "target_chapters": 5}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


SEAL = json.dumps({"volume_summary": "主角入了宗门。", "synopsis": "新梗概:入门完成。"}, ensure_ascii=False)


@pytest.fixture
def book(conn):
    return repo.create_book(conn, "诡仙")


def fill(conn, book, vid, n):
    start = repo.next_chapter_idx(conn, book)
    for i in range(start, start + n):
        cid = repo.create_chapter(conn, book, vid, i, title=f"T{i}")
        repo.update_chapter(conn, cid, body="b", summary=f"摘要{i}", status="accepted")


def test_plan_first_volume(conn, book):
    v = plan_volume(conn, FakeLLM([plan_json()]), S, book)
    assert v["idx"] == 1 and v["status"] == "active" and v["target_chapters"] == 5
    assert v["beats"] == ["拜师", "试炼"] and repo.active_volume(conn, book)["id"] == v["id"]


def test_target_chapters_out_of_range_uses_default(conn, book):
    v = plan_volume(conn, FakeLLM([plan_json(target_chapters=9999)]), S, book)
    assert v["target_chapters"] == 30


def test_plan_retries_bad_json_once(conn, book):
    v = plan_volume(conn, FakeLLM(["胡话", plan_json()]), S, book)
    assert v["goal"] == "入门"
    with pytest.raises(ChapterFailed):
        plan_volume(conn, FakeLLM(["x", "y"]), S, repo.create_book(conn, "b2"))


def test_plan_rejects_empty_beats(conn, book):
    with pytest.raises(ChapterFailed):
        plan_volume(conn, FakeLLM([plan_json(beats=[])] * 2), S, book)


def test_seal_updates_summary_and_synopsis_atomically(conn, book):
    v = plan_volume(conn, FakeLLM([plan_json()]), S, book)
    fill(conn, book, v["id"], 5)
    llm = FakeLLM([SEAL])
    seal_volume(conn, llm, S, book, v)
    assert repo.get_volume(conn, v["id"])["status"] == "sealed"
    assert repo.get_volume(conn, v["id"])["summary"] == "主角入了宗门。"
    assert repo.get_book(conn, book)["synopsis"] == "新梗概:入门完成。"
    assert "摘要1" in llm.calls[0][-1]["content"]  # 封卷时看到了本卷所有章摘要


def test_failed_seal_changes_nothing(conn, book):
    v = plan_volume(conn, FakeLLM([plan_json()]), S, book)
    fill(conn, book, v["id"], 5)
    with pytest.raises(ChapterFailed):
        seal_volume(conn, FakeLLM(["坏", "坏"]), S, book, v)
    assert repo.get_volume(conn, v["id"])["status"] == "active"


def test_ensure_keeps_volume_until_full_then_rolls_over(conn, book):
    v = ensure_active_volume(conn, FakeLLM([plan_json()]), S, book)  # 没有卷 → 规划第 1 卷
    fill(conn, book, v["id"], 4)
    assert ensure_active_volume(conn, FakeLLM([]), S, book)["id"] == v["id"]  # 没写满:不调 LLM
    fill(conn, book, v["id"], 1)
    nxt = ensure_active_volume(conn, FakeLLM([SEAL, plan_json(goal="下山")]), S, book)
    assert nxt["idx"] == 2 and nxt["goal"] == "下山"
    assert repo.get_volume(conn, v["id"])["status"] == "sealed"


def test_second_volume_plan_sees_sealed_summary(conn, book):
    v = ensure_active_volume(conn, FakeLLM([plan_json()]), S, book)
    fill(conn, book, v["id"], 5)
    llm = FakeLLM([SEAL, plan_json(goal="下山")])
    ensure_active_volume(conn, llm, S, book)
    plan_prompt = llm.calls[1][-1]["content"]
    assert "主角入了宗门。" in plan_prompt and "新梗概:入门完成。" in plan_prompt


def test_seal_with_facts_requires_canon_and_saves_it(conn, book):
    v = plan_volume(conn, FakeLLM([plan_json()]), S, book)
    fill(conn, book, v["id"], 5)
    repo.add_fact(conn, book, "后山有井", 2)
    with pytest.raises(ChapterFailed):  # 有事实却给空定本:拒绝,否则封卷后这条事实会从 prompt 消失
        seal_volume(conn, FakeLLM([SEAL, SEAL]), S, book, v)
    assert repo.get_volume(conn, v["id"])["status"] == "active"
    with_canon = json.dumps({"volume_summary": "卷摘要", "synopsis": "梗概", "canon": ["后山有井", "宗门禁夜行"]},
                            ensure_ascii=False)
    llm = FakeLLM([with_canon])
    seal_volume(conn, llm, S, book, v)
    assert repo.get_bible(conn, book)["canon"] == "后山有井\n宗门禁夜行"  # 数组形式被规整成每行一条
    assert "后山有井" in llm.calls[0][-1]["content"]  # 封卷时编辑看得到本卷事实
