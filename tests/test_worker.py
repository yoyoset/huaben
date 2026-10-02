import json
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from huaben import repo
from huaben.api.app import create_app
from huaben.config import Settings
from huaben.db import connect
from huaben.llm import LLMError
from huaben.llm_fake import FakeLLM
from huaben.worker import Backoff, Worker

PLAN = json.dumps({"goal": "g", "beats": ["a"], "plant": [], "resolve": [], "target_chapters": 30}, ensure_ascii=False)
OUTLINE = json.dumps({"title": "T", "outline": "事", "characters": [], "foreshadows": [],
                      "planned_reversals": [], "hook": "钩"}, ensure_ascii=False)
LEDGER = json.dumps({"summary": "摘要", "characters": [], "foreshadows_new": [], "foreshadows_update": [],
                     "facts": [], "contradictions": []}, ensure_ascii=False)
CHAPTER = [OUTLINE, "正文", LEDGER]


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_backoff_exponential_cap_and_reset():
    clk = Clock()
    b = Backoff(60, 200, clk)
    assert b.ready(1)
    b.record(1, ok=False)           # 退避 60
    assert not b.ready(1) and b.ready(2)
    clk.t = 60
    assert b.ready(1)
    b.record(1, ok=False)           # 退避 120
    clk.t = 60 + 119
    assert not b.ready(1)
    clk.t = 60 + 120
    b.record(1, ok=False)           # 240 → 被 cap 到 200
    clk.t += 199
    assert not b.ready(1)
    clk.t += 1
    assert b.ready(1)
    b.record(1, ok=True)            # 成功复位
    b.record(1, ok=False)
    clk.t += 60
    assert b.ready(1)


def make_state(tmp_path, replies, **kw):
    s = Settings(openrouter_api_key="x", chapter_words=1, data_dir=tmp_path, buffer_chapters=1, worker_enabled=False,
                 _env_file=None, **kw)
    conn = connect(s.db_path)
    bid = repo.create_book(conn, "书")
    repo.update_book(conn, bid, status="serializing")
    repo.create_book(conn, "草稿")  # drafting,不处理
    conn.close()
    return SimpleNamespace(settings=s, llm=FakeLLM(replies), tts=None), bid, s


def test_tick_fills_serializing_books_only(tmp_path):
    state, bid, s = make_state(tmp_path, [PLAN] + CHAPTER)
    res = Worker(state, 60, Backoff(60, 600)).tick()
    assert set(res) == {bid} and res[bid].generated == 1
    conn = connect(s.db_path)
    assert repo.buffered_ahead(conn, bid) == 1


def test_failure_backs_off_then_recovers(tmp_path):
    clk = Clock()
    state, bid, s = make_state(tmp_path, [LLMError("503")])
    w = Worker(state, 60, Backoff(60, 600, clk))
    assert w.tick()[bid].error                      # 第一次失败
    assert w.tick() == {}                           # 退避期内不再打 LLM(FakeLLM 已空,再打会断言失败)
    clk.t = 61
    state.llm._replies += [PLAN] + CHAPTER
    assert w.tick()[bid].generated == 1             # 退避结束,恢复
    assert w.tick()[bid].generated == 0             # 成功后已复位:继续被巡检(缓冲已满,无需再生成)


def test_tick_without_api_key_is_quiet(tmp_path):
    s = Settings(openrouter_api_key="", data_dir=tmp_path, worker_enabled=False, _env_file=None)
    connect(s.db_path).close()
    state = SimpleNamespace(settings=s, llm=None, tts=None)
    assert Worker(state, 60, Backoff(60, 600)).tick() == {}


def test_unexpected_exception_is_visible_and_backed_off(tmp_path):
    """程序缺陷(非 LLM/流水线错误)也要写进 gen_error 并退避,不能静默停更。"""
    clk = Clock()
    state, bid, s = make_state(tmp_path, [RuntimeError("意外")])
    w = Worker(state, 60, Backoff(60, 600, clk))
    res = w.tick()  # 不抛
    assert "程序内部出错" in res[bid].error
    conn = connect(s.db_path)
    assert "程序内部出错" in repo.get_book(conn, bid)["gen_error"]
    tech = conn.execute("SELECT note FROM pipeline_runs WHERE step='error'").fetchone()[0]
    assert "RuntimeError" in tech  # 技术细节在 pipeline_runs,不在界面上
    assert w.tick() == {}  # 已退避


def test_thread_recovers_after_restart_and_stops_cleanly(tmp_path):
    """服务"重启":库里已有连载中的书且缓冲为空,常驻线程启动后自己补齐。"""
    s = Settings(openrouter_api_key="x", chapter_words=1, data_dir=tmp_path, buffer_chapters=1, worker_enabled=True,
                 worker_interval_s=0.05, _env_file=None)
    conn = connect(s.db_path)
    bid = repo.create_book(conn, "书")
    repo.update_book(conn, bid, status="serializing")
    conn.close()
    with TestClient(create_app(s, llm=FakeLLM([PLAN] + CHAPTER))):
        deadline = time.time() + 5
        while time.time() < deadline:
            c = connect(s.db_path)
            n = repo.buffered_ahead(c, bid)
            c.close()
            if n >= 1:
                break
            time.sleep(0.05)
        assert n >= 1
    # 退出 with 后线程已停,不应残留
    assert not [t for t in __import__("threading").enumerate() if t.name == "huaben-worker" and t.is_alive()]


def test_audio_failure_does_not_hold_back_text(tmp_path):
    """审查实测:配音一直失败时,整本书被退避,读者往前读后文字缓冲不再补。现在两类各自退避。"""
    from huaben.tts.fake import FakeTTS
    clk = Clock()
    state, bid, s = make_state(tmp_path, [PLAN] + CHAPTER + CHAPTER, tts_retries=0)
    state.tts = FakeTTS(always_fail=True)
    w = Worker(state, 60, Backoff(60, 600, clk))
    r1 = w.tick()[bid]
    assert r1.generated == 1 and r1.audio_error
    conn = connect(s.db_path)
    repo.update_book(conn, bid, read_pos=1)          # 读者读完第 1 章
    r2 = w.tick()[bid]                                # 配音仍在退避,但文字照常补
    assert r2.generated == 1 and r2.audio_error == ""  # 本轮没尝试配音,不报也不清配音错误
    b = repo.get_book(conn, bid)
    assert b["gen_error"] == "" and "配音失败" in b["audio_error"]  # 配音错误仍可见


def test_audio_only_round_keeps_text_error_visible(tmp_path):
    """文字在退避、配音照常巡检的那一轮:只做配音,不能把文字错误清掉(否则读者以为好了)。"""
    from huaben.tts.fake import FakeTTS
    clk = Clock()
    state, bid, s = make_state(tmp_path, [LLMError("down", kind="server")], tts_retries=0)
    state.tts = FakeTTS()
    w = Worker(state, 60, Backoff(60, 600, clk))
    assert w.tick()[bid].error                 # 文字失败 → 文字退避
    r2 = w.tick()[bid]                          # 本轮只配音(没有章可配)
    assert r2.generated == 0 and r2.error == ""
    conn = connect(s.db_path)
    assert "暂时不可用" in repo.get_book(conn, bid)["gen_error"]  # 文字错误仍在
