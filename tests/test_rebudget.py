"""给已经在写的卷补章数预算(T004):merge_budget 纯函数 + rebudget 接口。"""
import json

import pytest

from huaben import repo
from huaben.beat_budget import locate, normalize_budget
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.pipeline.errors import ChapterFailed
from huaben.pipeline.rebudget import merge_budget, rebudget


@pytest.mark.parametrize("args,expected", [
    ((0, [1, 3, 2], 3, 4), [5, 3, 2]),
    ((2, [3], 3, 5), [3, 2, 3]),
    ((2, [3], 3, 1), [1, 0, 3]),   # 章比节拍少:前面的节拍摊到 0 章,locate 会跳过
])
def test_merge_budget_makes_a_full_list(args, expected):
    assert merge_budget(*args) == expected
    done_beats, remaining, beat_count, volume_done = args
    rest = normalize_budget(remaining, beat_count - done_beats)
    assert sum(expected) == volume_done + sum(rest)          # 总章数 = 已写 + 剩下的
    assert locate(expected, volume_done)[0] == done_beats + 1  # 从正在进行的节拍接着走


@pytest.mark.parametrize("args", [
    (3, [], 3, 5),        # 全走完了不合法
    (1, [3], 3, 5),       # remaining 长度不对
    ("1", [3, 2], 3, 5),  # done_beats 不是整数
])
def test_merge_budget_rejects_bad_shape(args):
    assert merge_budget(*args) is None


def _app(tmp_path, replies):
    from fastapi.testclient import TestClient

    from huaben.api.app import create_app
    from huaben.db import connect
    from huaben.tts.fake import FakeTTS
    s = Settings(openrouter_api_key="x", data_dir=tmp_path, worker_enabled=False, _env_file=None)
    conn = connect(s.db_path)
    bid = repo.create_book(conn, "书")
    vid = repo.create_volume(conn, bid, 1, beats=["镇上算账", "考场策论", "外门杂役"], status="active",
                             target_chapters=30)
    for i in range(1, 5):
        cid = repo.create_chapter(conn, bid, vid, i, title=f"T{i}")
        repo.update_chapter(conn, cid, body="b", summary=f"第{i}章摘要", status="accepted")
    c = TestClient(create_app(s, tts=FakeTTS()))
    c.app.state.llm = FakeLLM(replies)
    c.app.state.llm_injected = True
    return s, conn, bid, c


def test_rebudget_endpoint_updates_the_volume(tmp_path):
    _, conn, bid, c = _app(tmp_path, [json.dumps({"done_beats": 1, "remaining": [3, 2]}, ensure_ascii=False)])
    r = c.post(f"/api/books/{bid}/volume/budget").json()
    assert r == {"beat_chapters": [4, 3, 2], "target_chapters": 9, "done_beats": 1}
    v = repo.active_volume(conn, bid)
    assert v["beat_chapters"] == [4, 3, 2] and v["target_chapters"] == 9


class RecordingLLM:
    """记录每次调用的 temperature(现有替身不记,T009 要断言判断题用低温)。"""

    def __init__(self, reply):
        self.reply = reply
        self.temperatures = []

    def chat(self, messages, *, max_tokens=None, temperature=0.9, json_mode=False):
        from huaben.llm import LLMResult
        self.temperatures.append(temperature)
        return LLMResult(text=self.reply, tokens_in=1, tokens_out=1, cost_usd=0)


def _book_with_chapters(tmp_path):
    from huaben.db import connect
    s = Settings(openrouter_api_key="x", data_dir=tmp_path, _env_file=None)
    conn = connect(s.db_path)
    bid = repo.create_book(conn, "书")
    vid = repo.create_volume(conn, bid, 1, beats=["a", "b", "c"], status="active", target_chapters=30)
    for i in range(1, 5):
        cid = repo.create_chapter(conn, bid, vid, i, title=f"T{i}")
        repo.update_chapter(conn, cid, body="b", summary="s", status="accepted")
    return s, conn, bid


def test_rebudget_returns_done_beats_and_uses_low_temperature(tmp_path):
    s, conn, bid = _book_with_chapters(tmp_path)
    llm = RecordingLLM(json.dumps({"done_beats": 1, "remaining": [3, 2]}, ensure_ascii=False))
    r = rebudget(conn, llm, s, bid)
    assert r["done_beats"] == 1 and r["beat_chapters"] == [4, 3, 2]
    assert llm.temperatures == [0.2]  # 对照摘要判断走到哪了:低温


def test_plan_volume_still_uses_planning_temperature(tmp_path):
    from huaben.pipeline.volume import plan_volume
    s, conn, bid = _book_with_chapters(tmp_path)
    llm = RecordingLLM(json.dumps({"goal": "g", "beats": ["a", "b"], "plant": [], "resolve": [],
                                   "target_chapters": 10}, ensure_ascii=False))
    plan_volume(conn, llm, s, bid)
    assert llm.temperatures == [0.7]


def test_rebudget_bad_output_twice_is_502(tmp_path):
    _, _, bid, c = _app(tmp_path, ["胡话", "还是胡话"])
    assert c.post(f"/api/books/{bid}/volume/budget").status_code == 502


def test_rebudget_without_active_volume_raises(tmp_path):
    from huaben.db import connect
    s = Settings(openrouter_api_key="x", data_dir=tmp_path, _env_file=None)
    conn = connect(s.db_path)
    bid = repo.create_book(conn, "空书")
    with pytest.raises(ChapterFailed):
        rebudget(conn, FakeLLM([]), s, bid)
