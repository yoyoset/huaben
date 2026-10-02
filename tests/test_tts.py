import pytest

from huaben import repo
from huaben.config import Settings
from huaben.tts.base import TTSError
from huaben.tts.fake import FAKE_MP3_HEADER, FakeTTS
from huaben.tts.mp3 import is_mp3
from huaben.tts.service import (audio_relpath, ensure_chapter_audio, fill_audio, synthesize_text)
from huaben.tts.text import clean_for_tts, split_for_tts

NOSLEEP = lambda s: None  # noqa: E731


def settings(tmp_path, **kw):
    return Settings(openrouter_api_key="x", chapter_words=1, data_dir=tmp_path, _env_file=None, **kw)


def test_is_mp3():
    assert is_mp3(b"ID3\x03\x00") and is_mp3(b"\xff\xfb\x90\x00")
    assert not is_mp3(b"\x1a\x45\xdf\xa3")  # WebM/EBML
    assert not is_mp3(b"") and not is_mp3(b"abc")


def test_clean_for_tts():
    assert clean_for_tts("**他**说:`好`\n\n\n\n---\n走吧") == "他说:好\n\n走吧"


def test_split_keeps_all_text_and_respects_limit():
    text = "第一段。\n" + "很长的一句话" * 100 + "。第二句。第三句。\n结尾。"
    chunks = split_for_tts(text, 120)
    assert all(len(c) <= 120 for c in chunks)
    joined = "".join(chunks).replace("\n", "")
    assert joined == text.replace("\n", "")  # 不丢字不重复


def test_split_short_text_single_chunk_and_empty():
    assert split_for_tts("一句话。\n另一句。", 100) == ["一句话。\n另一句。"]
    assert split_for_tts("  \n ", 100) == []


def test_synthesize_concats_in_order(tmp_path):
    tts = FakeTTS()
    out = synthesize_text(tts, "甲。\n乙。\n丙。", settings(tmp_path, tts_chunk_chars=3), NOSLEEP)
    assert tts.calls == ["甲。", "乙。", "丙。"]
    assert out.count(FAKE_MP3_HEADER) == 3


def test_retry_then_succeed_and_exhaust(tmp_path):
    ok = synthesize_text(FakeTTS(fail_times=2), "一句。", settings(tmp_path), NOSLEEP)
    assert is_mp3(ok)
    with pytest.raises(TTSError):
        synthesize_text(FakeTTS(always_fail=True), "一句。", settings(tmp_path), NOSLEEP)


def test_non_mp3_output_fails_without_retry(tmp_path):
    class WebmTTS:
        calls = 0

        def synthesize(self, text):
            WebmTTS.calls += 1
            return b"\x1a\x45\xdf\xa3junk"

    with pytest.raises(TTSError, match="MP3"):
        synthesize_text(WebmTTS(), "一句。", settings(tmp_path), NOSLEEP)
    assert WebmTTS.calls == 1


def make_chapter(conn, idx=1, body="正文。", title="夜巡"):
    bid = repo.list_books(conn)[0]["id"] if repo.list_books(conn) else repo.create_book(conn, "书")
    vols = repo.list_volumes(conn, bid)
    vid = vols[0]["id"] if vols else repo.create_volume(conn, bid, 1, status="active")
    cid = repo.create_chapter(conn, bid, vid, idx, title=title)
    repo.update_chapter(conn, cid, body=body, summary="s", status="accepted")
    return repo.get_chapter(conn, bid, idx)


def test_ensure_writes_file_registers_and_is_idempotent(conn, tmp_path):
    s = settings(tmp_path)
    ch = make_chapter(conn)
    tts = FakeTTS()
    path = ensure_chapter_audio(conn, tts, s, ch, NOSLEEP)
    assert path == tmp_path / "audio" / audio_relpath(ch["book_id"], 1) and path.exists()
    assert "第1章,夜巡。" in path.read_bytes().decode("utf-8", "ignore")  # 开头报章名
    assert not list(path.parent.glob("*.tmp"))
    assert repo.get_audio(conn, ch["id"])["path"] == audio_relpath(ch["book_id"], 1)
    ensure_chapter_audio(conn, tts, s, ch, NOSLEEP)
    assert len(tts.calls) == 1  # 第二次不重复合成


def test_failure_logged_and_no_partial_file(conn, tmp_path):
    ch = make_chapter(conn)
    with pytest.raises(TTSError):
        ensure_chapter_audio(conn, FakeTTS(always_fail=True), settings(tmp_path), ch, NOSLEEP)
    assert repo.get_audio(conn, ch["id"]) is None
    assert not list((tmp_path / "audio").rglob("*.mp3*"))
    assert conn.execute("SELECT COUNT(*) FROM pipeline_runs WHERE step='tts' AND ok=0").fetchone()[0] == 1


def test_fill_audio_backfills_and_stops_on_failure(conn, tmp_path):
    s = settings(tmp_path)
    make_chapter(conn, 1)
    make_chapter(conn, 2)
    bid = repo.list_books(conn)[0]["id"]
    done, err = fill_audio(conn, FakeTTS(), s, bid, NOSLEEP)
    assert (done, err) == (2, "")
    make_chapter(conn, 3)
    done, err = fill_audio(conn, FakeTTS(always_fail=True), s, bid, NOSLEEP)
    assert done == 0 and "第 3 章配音失败" in err and "照常阅读" in err
    assert [c["idx"] for c in repo.chapters_missing_audio(conn, bid)] == [3]
