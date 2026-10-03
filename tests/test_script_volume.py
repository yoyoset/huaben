"""剧本制(二)卷剧本(T011):检查、代号翻译、导入、按剧本章纲写章。"""
import json
import re

import pytest

from huaben import repo
from huaben.config import Settings
from huaben.llm import LLMResult
from huaben.llm_fake import FakeLLM
from huaben.pipeline.chapter import generate_chapter
from huaben.pipeline.errors import ChapterFailed
from huaben.pipeline.volume import ensure_active_volume
from huaben.script_import import (ScriptImportError, check_volume_script, import_book, import_volume,
                                  resolve_keys)
from test_script_import import BOOK
from scripted_llm import body_for

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)


def ch(i=1, mode="战", tension=3, result="无", gain="", foreshadows=None, plant=None):
    return {"title": f"第{i}章标题", "outline": f"第{i}章的事", "when": "第二天", "characters": ["沈照"],
            "foreshadows": foreshadows or [], "planned_reversals": [], "payoff": "拿到线索", "novelty": "",
            "hook": "门口有人", "mode": mode, "tension": tension, "result": result, "gain": gain,
            **({"plant": plant} if plant else {})}


def vol(chapters, beats=("起", "承"), budget=(1, 1), **kw):
    return {"volume": {"goal": "入门", "beats": list(beats), "beat_chapters": list(budget)},
            "chapters": chapters, **kw}


def test_check_volume_script_accepts_a_good_script():
    data = {"volume": {"goal": "入门", "beats": ["起", "承"], "beat_chapters": [1, 1]},
            "chapters": [ch(1), ch(2, plant={"key": "F1", "content": "旧信", "truth": "父亲写的"})]}
    assert check_volume_script(data, set()) == []


@pytest.mark.parametrize("data,needle", [
    ({"volume": {"goal": "g", "beats": ["a"], "beat_chapters": [1]}, "chapters": []}, "没有章纲"),
    ({"volume": {"goal": "g", "beats": ["a"], "beat_chapters": [1]}, "chapters": [ch(1), ch(2)]}, "只能再放"),
    ({"volume": {"goal": "g", "beats": ["a"], "beat_chapters": [1, 2]}, "chapters": [ch(1)]}, "beat_chapters 必须"),
    ({"chapters": [{"title": "T", "outline": "事", "payoff": "p", "hook": "h"}]}, "缺 when"),
    ({"chapters": [ch(1, foreshadows=["FX"])]}, "还没埋下"),
    ({"chapters": [ch(1), ch(1)]}, "标题重复"),
    ({"chapters": [ch(1, plant={"key": "F1", "content": "a"})]}, "plant 缺"),
    ({"chapters": [ch(1, plant={"key": "F1", "content": "a", "truth": "b"}),
                   ch(2, plant={"key": "F1", "content": "c", "truth": "d"})]}, "重复"),
])
def test_check_volume_script_reports(data, needle):
    assert any(needle in p for p in check_volume_script(data, set()))


def test_resolve_keys_translates_and_reports_missing():
    new, missing = resolve_keys({"foreshadows": ["F1", 7, "F9"]}, {"F1": 3})
    assert new["foreshadows"] == [3, 7] and missing == ["F9"]


def test_import_volume_opens_a_volume(conn):
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    r = import_volume(conn, FakeLLM([]), S, bid, vol([ch(1), ch(2)]))
    assert r == {"volume_idx": 1, "chapters": [1, 2], "rhythm_warnings": []}
    v = repo.active_volume(conn, bid)
    assert v["beat_chapters"] == [1, 1] and v["target_chapters"] == 2
    assert repo.get_scripted_outline(conn, bid, 1)["title"] == "第1章标题"
    assert repo.get_scripted_outline(conn, bid, 1)["mode"] == "战"  # 节奏标记原样存进库


def test_import_volume_rejects_non_scripted_book(conn):
    bid = repo.create_book(conn, "普通")
    with pytest.raises(ScriptImportError, match="不是剧本书"):
        import_volume(conn, FakeLLM([]), S, bid, vol([ch(1)]))


def test_import_volume_with_volume_while_current_unfinished(conn):
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    import_volume(conn, FakeLLM([]), S, bid, {"volume": {"goal": "g", "beats": ["a"], "beat_chapters": [3]},
                                              "chapters": [ch(1)]})
    with pytest.raises(ScriptImportError, match="还没写完"):
        import_volume(conn, FakeLLM([]), S, bid, vol([ch(2)]))


def test_import_volume_check_failure_writes_nothing(conn):
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    with pytest.raises(ScriptImportError) as ei:
        import_volume(conn, FakeLLM([]), S, bid,
                      {"volume": {"goal": "g", "beats": ["a"], "beat_chapters": [1]}, "chapters": [ch(1), ch(2)]})
    assert ei.value.problems and repo.list_volumes(conn, bid) == [] and repo.max_scripted_idx(conn, bid) == 0


def test_import_volume_continue_without_volume_needs_a_volume(conn):
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    with pytest.raises(ScriptImportError, match="没有进行中的卷"):
        import_volume(conn, FakeLLM([]), S, bid, {"chapters": [ch(1)]})


class ScriptOnlyLLM:
    """只提供正文/入账/封卷回复;被要章纲或卷规划就失败(剧本书不该让模型做这些)。"""

    def __init__(self):
        self.write_prompts = {}
        self.calls = []

    def chat(self, messages, *, max_tokens=None, temperature=0.9, json_mode=False):
        user = messages[-1]["content"]
        self.calls.append(user)
        if m := re.search(r"现在写第 (\d+) 章正文", user):
            n = int(m[1])
            self.write_prompts[n] = user
            return _r(f"（第{n}章）{body_for(n)}")
        if m := re.search(r"【第 (\d+) 章正文】", user):
            n = int(m[1])
            return _r(json.dumps({"summary": f"第{n}章摘要", "characters": [{"name": "沈照"}], "foreshadows_new": [],
                                  "foreshadows_update": [], "facts": [], "contradictions": []}, ensure_ascii=False))
        if "请封卷" in user:
            return _r(json.dumps({"volume_summary": "卷摘要", "synopsis": "梗概", "canon": ""}, ensure_ascii=False))
        raise AssertionError("剧本书不该让模型做这个: " + user[:60])


def _r(text):
    return LLMResult(text=text, tokens_in=1, tokens_out=1, cost_usd=0)


def test_batches_then_waits_for_next_batch(conn):
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    first = {"volume": {"goal": "g", "beats": ["a", "b"], "beat_chapters": [2, 3]},
             "chapters": [ch(1, plant={"key": "F1", "content": "旧信", "truth": "父亲写的"}), ch(2)]}
    import_volume(conn, FakeLLM([]), S, bid, first)
    llm = ScriptOnlyLLM()
    generate_chapter(conn, llm, S, bid)
    generate_chapter(conn, llm, S, bid)
    with pytest.raises(ChapterFailed) as ei:  # 第 3 章:这一批只有 2 章,等下一批
        generate_chapter(conn, llm, S, bid)
    assert ei.value.step == "script" and "下一批剧本" in str(ei.value)
    assert repo.active_volume(conn, bid)["status"] == "active"  # 没有封卷
    assert repo.list_volumes(conn, bid)[0]["status"] == "active"
    with pytest.raises(ScriptImportError, match="只能再放"):  # 续批超出 room(5−2=3)
        import_volume(conn, FakeLLM([]), S, bid, {"chapters": [ch(3), ch(4), ch(5), ch(6)]})
    r = import_volume(conn, FakeLLM([]), S, bid, {"chapters": [ch(3, foreshadows=["F1"]), ch(4), ch(5)]})
    assert r["chapters"] == [3, 5]  # 章号接着第一批
    for _ in range(3):
        generate_chapter(conn, llm, S, bid)
    assert [repo.get_chapter(conn, bid, i)["title"] for i in (3, 4, 5)] == ["第3章标题", "第4章标题", "第5章标题"]


def test_end_to_end_scripted_book_writes_to_script_then_waits(conn):
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    import_volume(conn, FakeLLM([]), S, bid, {
        "volume": {"goal": "入门", "beats": ["起"], "beat_chapters": [3]},
        "chapters": [ch(1, plant={"key": "F1", "content": "旧信", "truth": "父亲写的", "scale": "short"}),
                     ch(2), ch(3, foreshadows=["F1"])]})
    llm = ScriptOnlyLLM()
    for _ in range(3):
        generate_chapter(conn, llm, S, bid)
    assert [repo.get_chapter(conn, bid, i)["title"] for i in (1, 2, 3)] == \
           ["第1章标题", "第2章标题", "第3章标题"]
    fs = repo.list_foreshadows(conn, bid)
    assert len(fs) == 1 and fs[0]["key"] == "F1"
    assert "旧信" in llm.write_prompts[3]  # 第 3 章工单带出了 F1 的伏笔内容
    with pytest.raises(ChapterFailed) as ei:  # 第 4 章:先封卷,再等下一卷剧本
        ensure_active_volume(conn, llm, S, bid)
    assert ei.value.step == "script"
    assert repo.list_volumes(conn, bid)[0]["status"] == "sealed"
    assert not any("请规划第" in c for c in llm.calls)  # 没有卷规划的模型调用
