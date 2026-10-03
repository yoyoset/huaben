"""出门前预备 N 章(2026-10-03 用户:跑步前下好 10 章、20 章离线听)。"""
from huaben import repo
from huaben.prep import book_buffer_target, buffer_target, prep_range, prep_view
from test_voice_api import setup


def test_range_starts_at_current_chapter_and_is_capped():
    assert prep_range(5, 10) == (5, 14)
    assert prep_range(0, 10) == (1, 10)       # 还没读过:从第 1 章
    assert prep_range(1, 999) == (1, 50)      # 一次最多 50 章


def test_buffer_target_rises_while_preparing_then_falls_back():
    assert buffer_target(3, read_pos=5, prep_until=0) == 3     # 平时
    assert buffer_target(3, read_pos=5, prep_until=24) == 19   # 预备到 24 章:要比读到的多写 19 章
    assert buffer_target(3, read_pos=23, prep_until=24) == 3   # 读到了:回落到默认
    assert book_buffer_target({"read_pos": 5, "prep_until": 24}, 3) == 19


def test_view_counts_text_and_audio():
    v = prep_view(5, 7, [{"idx": 5, "has_audio": True}, {"idx": 6, "has_audio": False}])
    assert (v["total"], v["text_ready"], v["audio_ready"], v["done"]) == (3, 2, 1, False)


def test_prepare_api_sets_target_and_lists_downloadable_audio(tmp_path):
    s, conn, (a, b), c = setup(tmp_path, buffer_chapters=1)   # 甲 3 章,正在第 2 章
    v = c.post(f"/api/books/{a}/prepare", json={"count": 10}).json()
    assert (v["start"], v["end"], v["text_ready"], v["active"]) == (2, 11, 2, True)
    assert repo.get_book(conn, a)["prep_until"] == 11
    assert all(ch["audio_url"] is None for ch in v["chapters"])  # 还没配音:没有可下的
    mp3 = bytes([0xFF, 0xFB, 0x90, 0x00]) + bytes(413)
    c.put(f"/api/voice/jobs/{a}/2", content=mp3)
    v = c.get(f"/api/books/{a}/prepare").json()
    assert v["audio_ready"] == 1 and v["chapters"][0]["audio_url"].startswith(f"/api/books/{a}/chapters/2/audio?v=")
    assert c.get(v["chapters"][0]["audio_url"]).content == mp3
    assert c.post(f"/api/books/{a}/prepare", json={"count": 0}).status_code == 422


def test_android_app_is_served_from_data_dir(tmp_path):
    s, conn, books, c = setup(tmp_path)
    assert c.get("/api/app/huaben.apk").status_code == 404          # 还没发布:说清楚,不是 500
    (s.data_dir / "app").mkdir()
    (s.data_dir / "app" / "huaben.apk").write_bytes(b"PK\x03\x04apk")
    r = c.get("/api/app/huaben.apk")
    assert r.status_code == 200 and r.content == b"PK\x03\x04apk"
    assert r.headers["content-type"] == "application/vnd.android.package-archive"
