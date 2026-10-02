import json

import pytest
from fastapi.testclient import TestClient

from huaben.api.app import create_app
from huaben.config import Settings
from huaben.llm import LLMError
from huaben.llm_fake import FakeLLM
from huaben.tts.fake import FakeTTS

BIBLE = json.dumps({
    "title": "夜行录", "genre": "古代恐怖", "synopsis": "梗概", "world": "世界", "style_fingerprint": "短句",
    "characters": [{"name": "沈照", "role": "主角", "traits": "腹黑"}], "core_characters": ["沈照"], "taboos": [],
}, ensure_ascii=False)
PLAN = json.dumps({"goal": "入门", "beats": ["a"], "plant": [], "resolve": [], "target_chapters": 30}, ensure_ascii=False)
OUTLINE = json.dumps({"title": "夜巡", "outline": "事", "characters": [], "foreshadows": [],
                      "planned_reversals": [], "hook": "钩"}, ensure_ascii=False)
LEDGER = json.dumps({"summary": "摘要", "characters": [], "foreshadows_new": [], "foreshadows_update": [],
                     "facts": [], "contradictions": []}, ensure_ascii=False)
GUIDE = json.dumps({"reply": "喜欢什么题材?", "ready": False}, ensure_ascii=False)


def make_client(tmp_path, replies=(), tts=None, **kw):
    s = Settings(openrouter_api_key="x", chapter_words=1, data_dir=tmp_path, buffer_chapters=1, _env_file=None, **kw)
    llm = FakeLLM(list(replies))
    return TestClient(create_app(s, llm=llm, tts=tts)), llm


def open_book(c, title="未命名"):
    return c.post("/api/books", json={"title": title}).json()["id"]


def test_health_and_empty_shelf(tmp_path):
    c, _ = make_client(tmp_path)
    assert c.get("/api/health").json()["ok"] is True
    assert c.get("/api/books").json() == []


def test_create_and_get_book(tmp_path):
    c, _ = make_client(tmp_path)
    r = c.post("/api/books", json={"title": "测试书"})
    assert r.status_code == 201 and r.json()["status"] == "drafting" and r.json()["title"] == "测试书"
    assert c.get(f"/api/books/{r.json()['id']}").json()["ready_chapters"] == 0
    assert c.get("/api/books/999").status_code == 404


def test_opening_dialogue(tmp_path):
    c, _ = make_client(tmp_path, [GUIDE])
    bid = open_book(c)
    r = c.post(f"/api/books/{bid}/opening", json={"message": "古代恐怖"})
    assert r.status_code == 200 and r.json() == {"reply": "喜欢什么题材?", "ready": False}
    hist = c.get(f"/api/books/{bid}/opening").json()
    assert [m["role"] for m in hist] == ["user", "assistant"]
    assert c.post(f"/api/books/{bid}/opening", json={"message": ""}).status_code == 422


def test_finalize_without_conversation_is_400(tmp_path):
    c, _ = make_client(tmp_path)
    assert c.post(f"/api/books/{open_book(c)}/finalize").status_code == 400


def test_finalize_failure_is_502_and_retryable(tmp_path):
    c, _ = make_client(tmp_path, [GUIDE, "坏", "坏"])
    bid = open_book(c)
    c.post(f"/api/books/{bid}/opening", json={"message": "古代恐怖"})
    r = c.post(f"/api/books/{bid}/finalize")
    assert r.status_code == 502 and "再试一次" in r.json()["detail"] and "自动重试" not in r.json()["detail"]
    assert c.get(f"/api/books/{bid}").json()["status"] == "drafting"


def test_full_flow_open_book_then_read_and_listen(tmp_path):
    replies = [GUIDE, BIBLE, PLAN, OUTLINE, "这是第一章的正文。", LEDGER]
    c, llm = make_client(tmp_path, replies, tts=FakeTTS())
    bid = open_book(c)
    c.post(f"/api/books/{bid}/opening", json={"message": "古代恐怖"})
    book = c.post(f"/api/books/{bid}/finalize").json()
    assert book["status"] == "serializing" and book["title"] == "夜行录"
    # 后台补货在响应后执行:第 1 章已定稿并配好音
    assert c.get(f"/api/books/{bid}").json()["ready_chapters"] == 1
    assert c.get(f"/api/books/{bid}/chapters").json() == [{"idx": 1, "title": "夜巡", "has_audio": True}]
    ch = c.get(f"/api/books/{bid}/chapters/1").json()
    assert ch["body"] == "这是第一章的正文。" and ch["audio_url"].endswith("/chapters/1/audio")
    assert "outline" not in ch  # 章纲是内部工单,读者不可见
    a = c.get(ch["audio_url"])
    assert a.status_code == 200 and a.headers["content-type"] == "audio/mpeg" and a.content[:3] == b"ID3"
    assert c.get(f"/api/books/{bid}/stats").json()["chapters"] == 1


def test_audio_supports_range_requests(tmp_path):
    c, _ = make_client(tmp_path, [GUIDE, BIBLE, PLAN, OUTLINE, "正文。", LEDGER], tts=FakeTTS())
    bid = open_book(c)
    c.post(f"/api/books/{bid}/opening", json={"message": "x"})
    c.post(f"/api/books/{bid}/finalize")
    url = f"/api/books/{bid}/chapters/1/audio"
    full = c.get(url).content
    part = c.get(url, headers={"Range": "bytes=0-3"})
    assert part.status_code == 206 and part.content == full[:4]  # iOS <audio> 分段取流的前提
    assert part.headers["content-range"].startswith("bytes 0-3/")


def test_unwritten_chapter_and_audio_404(tmp_path):
    c, _ = make_client(tmp_path)
    bid = open_book(c)
    assert c.get(f"/api/books/{bid}/chapters/1").status_code == 404
    assert c.get(f"/api/books/{bid}/chapters/1/audio").status_code == 404


def test_progress_validates_and_triggers_refill(tmp_path):
    replies = [GUIDE, BIBLE, PLAN, OUTLINE, "一", LEDGER]
    c, llm = make_client(tmp_path, replies)
    bid = open_book(c)
    c.post(f"/api/books/{bid}/opening", json={"message": "x"})
    c.post(f"/api/books/{bid}/finalize")
    assert c.put(f"/api/books/{bid}/progress", json={"chapter": 5}).status_code == 404  # 没写到那章
    assert c.put(f"/api/books/{bid}/progress", json={"chapter": 0}).status_code == 422
    llm._replies += [OUTLINE, "二", LEDGER]  # 打开第 1 章 → 最远进度前进 → 缓冲变空 → 补第 2 章
    assert c.put(f"/api/books/{bid}/progress", json={"chapter": 1}).json() == {"read_pos": 1, "last_opened": 1}
    assert c.get(f"/api/books/{bid}").json()["ready_chapters"] == 2


def test_rereading_earlier_chapter_does_not_rewind_progress(tmp_path):
    """边听第 2 章边翻回第 1 章看:续读位置变成 1,但最远进度仍是 2,不触发补货、不误判缓冲。"""
    replies = [GUIDE, BIBLE, PLAN, OUTLINE, "一", LEDGER]
    c, llm = make_client(tmp_path, replies)
    bid = open_book(c)
    c.post(f"/api/books/{bid}/opening", json={"message": "x"})
    c.post(f"/api/books/{bid}/finalize")
    llm._replies += [OUTLINE, "二", LEDGER, OUTLINE, "三", LEDGER]
    c.put(f"/api/books/{bid}/progress", json={"chapter": 1})
    c.put(f"/api/books/{bid}/progress", json={"chapter": 2})
    calls = len(llm.calls)
    assert c.put(f"/api/books/{bid}/progress", json={"chapter": 1}).json() == {"read_pos": 2, "last_opened": 1}
    assert len(llm.calls) == calls  # 往回翻不触发补货
    book = c.get(f"/api/books/{bid}").json()
    assert book["read_pos"] == 2 and book["last_opened"] == 1


def test_missing_llm_key_gives_503_not_500(tmp_path):
    s = Settings(openrouter_api_key="", data_dir=tmp_path, _env_file=None)
    c = TestClient(create_app(s))
    bid = c.post("/api/books", json={}).json()["id"]
    r = c.post(f"/api/books/{bid}/opening", json={"message": "hi"})
    assert r.status_code == 503 and "API_KEY" in r.json()["detail"]


def test_generating_flag_tracks_buffer(tmp_path):
    c, llm = make_client(tmp_path, [GUIDE, BIBLE, PLAN, OUTLINE, "一", LEDGER])  # buffer_chapters=1
    bid = open_book(c)
    assert c.get(f"/api/books/{bid}").json()["generating"] is False  # 开书中:不在生成
    c.post(f"/api/books/{bid}/opening", json={"message": "x"})
    c.post(f"/api/books/{bid}/finalize")
    assert c.get(f"/api/books/{bid}").json()["generating"] is False  # 缓冲已满(1 章)
    llm._replies += [LLMError("down", kind="server")] * 3
    c.put(f"/api/books/{bid}/progress", json={"chapter": 1})       # 读完 → 缓冲空,补货失败
    assert c.get(f"/api/books/{bid}").json()["generating"] is True  # 前端据此继续自动刷新



def test_has_audio_reflects_file_presence(tmp_path):
    """数据库登记了音频但文件丢失:目录与章节都不能说"有音频",否则播放器会去取一个 404。"""
    c, _ = make_client(tmp_path, [GUIDE, BIBLE, PLAN, OUTLINE, "正文。", LEDGER], tts=FakeTTS())
    bid = open_book(c)
    c.post(f"/api/books/{bid}/opening", json={"message": "x"})
    c.post(f"/api/books/{bid}/finalize")
    assert c.get(f"/api/books/{bid}/chapters").json()[0]["has_audio"] is True
    next((tmp_path / "audio").rglob("*.mp3")).unlink()
    assert c.get(f"/api/books/{bid}/chapters").json()[0]["has_audio"] is False
    assert c.get(f"/api/books/{bid}/chapters/1").json()["audio_url"] is None
