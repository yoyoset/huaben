"""换音色:已经配过的章,读者还没听到的要换成新音色;听过的不动;旧文件在新文件登记后才删。
(2026-10-02 用户嫌 Kokoro 音色差、换 Qwen3-TTS:没有这条,已配好的章永远停在旧音色。)"""
from huaben import repo
from huaben.tts.store import audio_relpath
from test_voice_api import setup

MP3 = bytes([0xFF, 0xFB, 0x90, 0x00]) + bytes(413)


def _voice_all(c, s, conn, book, voice):
    for job in c.get("/api/voice/jobs", params={"limit": 10, "voice": voice}).json():
        assert c.put(f"/api/voice/jobs/{job['book_id']}/{job['idx']}", params={"voice": voice}, content=MP3).status_code == 200


def test_new_voice_redoes_only_unheard_chapters_and_replaces_files(tmp_path):
    s, conn, (a, b), c = setup(tmp_path)          # 甲 3 章,读到第 2 章
    _voice_all(c, s, conn, a, "kokoro-zh:zf_001")
    assert c.get("/api/voice/jobs", params={"voice": "kokoro-zh:zf_001"}).json() == []  # 同音色:没活

    jobs = c.get("/api/voice/jobs", params={"limit": 10, "voice": "qwen3-zh:Serena"}).json()
    # 甲第 1 章听过了,不重配;乙还没开始读,两章都要换
    assert sorted((j["book_id"], j["idx"]) for j in jobs) == [(a, 2), (a, 3), (b, 1), (b, 2)]
    jobs_b = [j for j in c.get("/api/voice/jobs", params={"limit": 10}).json()]
    assert jobs_b == []                            # 不报音色的老程序:行为不变,只配缺的

    old = repo.get_audio(conn, repo.get_chapter(conn, a, 2)["id"], "hq")["path"]
    assert c.put(f"/api/voice/jobs/{a}/2", params={"voice": "qwen3-zh:Serena"}, content=MP3).status_code == 200
    new = repo.get_audio(conn, repo.get_chapter(conn, a, 2)["id"], "hq")
    assert new["voice"] == "qwen3-zh:Serena" and new["path"] == audio_relpath(a, 2, "hq", "qwen3-zh:Serena") != old
    assert (s.audio_dir / new["path"]).is_file() and not (s.audio_dir / old).exists()  # 地址变了,浏览器不会播缓存的旧音色
    url = c.get(f"/api/books/{a}/chapters/2").json()["audio_url"]
    assert new["path"].replace("/", "_") in url
