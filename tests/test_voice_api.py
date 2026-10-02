"""电脑配音程序(拉取模式)与"电脑没开先用 edge"(2026-10-02 用户定:以电脑上的中文模型为主)。"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from huaben import repo
from huaben.api.app import create_app
from huaben.api.deps import auto_tts
from huaben.config import Settings
from huaben.db import connect
from huaben.tts.fake import FakeTTS
from huaben.voice_queue import interleave

MP3 = bytes([0xFF, 0xFB, 0x90, 0x00]) + bytes(413)  # 一帧合法的 MP3


def setup(tmp_path, **kw):
    s = Settings(openrouter_api_key="x", data_dir=tmp_path, worker_enabled=False, _env_file=None, **kw)
    conn = connect(s.db_path)
    books = []
    for title, n, at in (("甲", 3, 2), ("乙", 2, 0)):
        bid = repo.create_book(conn, title)
        repo.update_book(conn, bid, status="serializing", last_opened=at, read_pos=at)
        vid = repo.create_volume(conn, bid, 1, status="active")
        for i in range(1, n + 1):
            cid = repo.create_chapter(conn, bid, vid, i, title=f"{title}{i}")
            repo.update_chapter(conn, cid, body=f"{title}第{i}章正文。", summary="s", status="accepted")
        books.append(bid)
    return s, conn, books, TestClient(create_app(s, tts=FakeTTS()))


def test_interleave_takes_each_books_most_urgent_first():
    assert interleave([[1, 2, 3], [10, 11], []], 4) == [1, 10, 2, 11]
    assert interleave([[1, 2], [10]], 10) == [1, 10, 2]
    assert interleave([], 3) == []


def test_jobs_follow_listening_order_across_books_and_mark_pc_online(tmp_path):
    s, conn, (a, b), c = setup(tmp_path)
    assert c.get("/api/voice/status").json()["worker_online"] is False
    jobs = c.get("/api/voice/jobs?limit=4").json()
    # 甲读到第 2 章 → 2,3,1;乙没读过 → 1,2;两本轮流
    assert [(j["book_id"], j["idx"]) for j in jobs] == [(a, 2), (b, 1), (a, 3), (b, 2)]
    assert jobs[0]["text"].startswith("第2章,甲2。") and "正文" in jobs[0]["text"]
    st = c.get("/api/voice/status").json()
    assert st["worker_online"] is True and st["mode"] == "pc" and st["pending"] == 5


def test_uploaded_pc_audio_is_preferred_and_removed_from_queue(tmp_path):
    s, conn, (a, b), c = setup(tmp_path)
    c.post(f"/api/voice/fallback/{a}")                 # 先用 edge 顶着
    assert c.put(f"/api/voice/jobs/{a}/2", content=MP3).json() == {"ok": True}
    url = c.get(f"/api/books/{a}/chapters/2").json()["audio_url"]
    assert "hq" in url and c.get(url).content == MP3  # 电脑版优先;edge 版仍保留
    assert repo.get_audio(conn, repo.get_chapter(conn, a, 2)["id"], "basic") is not None
    assert (a, 2) not in [(j["book_id"], j["idx"]) for j in c.get("/api/voice/jobs?limit=10").json()]


def test_bad_uploads_are_rejected(tmp_path):
    s, conn, (a, _), c = setup(tmp_path)
    assert c.put(f"/api/voice/jobs/{a}/1", content=b"RIFF....WAVE").status_code == 415
    assert c.put(f"/api/voice/jobs/{a}/1", content=b"").status_code == 400
    assert c.put(f"/api/voice/jobs/{a}/99", content=MP3).status_code == 404


def test_token_is_required_when_configured(tmp_path):
    s, conn, (a, _), c = setup(tmp_path, voice_worker_token="t0k")
    assert c.get("/api/voice/jobs").status_code == 401
    assert c.get("/api/voice/jobs", headers={"Authorization": "Bearer t0k"}).status_code == 200


def test_fallback_voices_only_chapters_with_no_audio_at_all(tmp_path):
    s, conn, (a, _), c = setup(tmp_path)
    c.put(f"/api/voice/jobs/{a}/1", content=MP3)       # 第 1 章已有电脑版
    assert c.get(f"/api/books/{a}").json()["audio_pending"] == 2
    assert c.post(f"/api/voice/fallback/{a}").status_code == 202
    assert c.get(f"/api/books/{a}").json()["audio_pending"] == 0
    assert repo.get_audio(conn, repo.get_chapter(conn, a, 1)["id"], "basic") is None  # 不重复配


@pytest.mark.parametrize("mode,expected", [("pc", None), ("edge", "tts")])
def test_server_voices_automatically_only_in_edge_mode(mode, expected):
    state = SimpleNamespace(settings=SimpleNamespace(tts_mode=mode), tts="tts")
    assert auto_tts(state) == expected
