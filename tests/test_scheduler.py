import json
import threading

from huaben import repo
from huaben.config import Settings
from huaben.llm import LLMError
from huaben.llm_fake import FakeLLM
from huaben.scheduler import _lock_for, top_up, top_up_all

S = Settings(openrouter_api_key="x", chapter_words=1, buffer_chapters=2, _env_file=None)

PLAN = json.dumps({"goal": "g", "beats": ["a"], "plant": [], "resolve": [], "target_chapters": 30}, ensure_ascii=False)
OUTLINE = json.dumps({"title": "T", "outline": "事", "characters": [], "foreshadows": [],
                      "planned_reversals": [], "hook": "钩"}, ensure_ascii=False)
LEDGER = json.dumps({"summary": "摘要", "characters": [], "foreshadows_new": [], "foreshadows_update": [],
                     "facts": [], "contradictions": []}, ensure_ascii=False)


def chapter_replies(n):
    return [OUTLINE, "正文", LEDGER] * n


def serializing_book(conn, title="书"):
    bid = repo.create_book(conn, title)
    repo.update_book(conn, bid, status="serializing")
    return bid


def test_top_up_fills_buffer_including_first_volume(conn):
    bid = serializing_book(conn)
    res = top_up(conn, FakeLLM([PLAN] + chapter_replies(2)), S, bid)
    assert res.generated == 2 and res.error == "" and not res.skipped
    assert repo.buffered_ahead(conn, bid) == 2


def test_top_up_is_noop_when_buffer_full(conn):
    bid = serializing_book(conn)
    top_up(conn, FakeLLM([PLAN] + chapter_replies(2)), S, bid)
    assert top_up(conn, FakeLLM([]), S, bid).generated == 0  # 不调 LLM


def test_reader_progress_triggers_refill(conn):
    bid = serializing_book(conn)
    top_up(conn, FakeLLM([PLAN] + chapter_replies(2)), S, bid)
    repo.update_book(conn, bid, read_pos=1)  # 读完一章,缓冲只剩 1
    res = top_up(conn, FakeLLM(chapter_replies(1)), S, bid)
    assert res.generated == 1 and repo.buffered_ahead(conn, bid) == 2


def test_failure_stops_loop_and_is_visible(conn):
    bid = serializing_book(conn)
    llm = FakeLLM([PLAN] + chapter_replies(1) + [LLMError("HTTP 503: upstream", kind="server", status=503)] * 3)
    res = top_up(conn, llm, S, bid)
    assert res.generated == 1 and "模型服务暂时不可用" in res.error
    shown = repo.get_book(conn, bid)["gen_error"]
    assert "模型服务暂时不可用" in shown and "自动重试" in shown  # 界面可见、是人话、说明了用户要不要做什么
    assert "503" not in shown and "HTTP" not in shown                # 技术细节不上界面
    tech = conn.execute("SELECT note FROM pipeline_runs WHERE step='error'").fetchone()[0]
    assert "HTTP 503" in tech                                         # 而是留在 pipeline_runs


def test_success_clears_previous_error(conn):
    bid = serializing_book(conn)
    repo.update_book(conn, bid, gen_error="旧错误")
    top_up(conn, FakeLLM([PLAN] + chapter_replies(2)), S, bid)
    assert repo.get_book(conn, bid)["gen_error"] == ""


def test_max_chapters_bounds_one_call(conn):
    bid = serializing_book(conn)
    res = top_up(conn, FakeLLM([PLAN] + chapter_replies(1)), S, bid, max_chapters=1)
    assert res.generated == 1 and repo.buffered_ahead(conn, bid) == 1


def test_concurrent_top_up_is_skipped(conn):
    bid = serializing_book(conn)
    lock = _lock_for(bid)
    lock.acquire()
    try:
        out = {}
        t = threading.Thread(target=lambda: out.update(r=top_up(conn, FakeLLM([]), S, bid)))
        t.start()
        t.join()
        assert out["r"].skipped
    finally:
        lock.release()


def test_top_up_all_only_serializing_and_isolated_failures(conn):
    a = serializing_book(conn, "a")
    repo.create_book(conn, "draft")  # drafting,不处理
    b = serializing_book(conn, "b")
    llm = FakeLLM([LLMError("boom")] + [PLAN] + chapter_replies(2))
    out = top_up_all(conn, llm, S)
    assert set(out) == {a, b}
    assert out[a].error and out[b].generated == 2  # a 失败不拖累 b


def test_top_up_also_voices_chapters(conn, tmp_path):
    from huaben.tts.fake import FakeTTS
    s = Settings(openrouter_api_key="x", chapter_words=1, buffer_chapters=2, data_dir=tmp_path, _env_file=None)
    bid = serializing_book(conn)
    res = top_up(conn, FakeLLM([PLAN] + chapter_replies(2)), s, bid, tts=FakeTTS())
    assert res.generated == 2 and res.audio_error == ""
    assert repo.chapters_missing_audio(conn, bid) == []


def test_tts_failure_does_not_block_text_but_is_visible(conn, tmp_path):
    from huaben.tts.fake import FakeTTS
    s = Settings(openrouter_api_key="x", chapter_words=1, buffer_chapters=2, data_dir=tmp_path, tts_retries=0, _env_file=None)
    bid = serializing_book(conn)
    res = top_up(conn, FakeLLM([PLAN] + chapter_replies(2)), s, bid, tts=FakeTTS(always_fail=True))
    assert res.generated == 2 and "配音失败" in res.audio_error
    b = repo.get_book(conn, bid)
    assert "配音失败" in b["audio_error"] and b["gen_error"] == ""  # 两类错误分开存,文字没问题就不报文字错误
