"""电脑端配音程序(pc_worker/huaben_voice)对着真的服务器接口跑:FastAPI 的 TestClient 本身就是 httpx.Client。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pc_worker"))

from huaben_voice.client import ServerError, VoiceClient  # noqa: E402
from huaben_voice.engines import FakeEngine, create_engine  # noqa: E402
from huaben_voice.loop import run_forever, run_once  # noqa: E402

from huaben import repo  # noqa: E402
from test_voice_api import setup  # noqa: E402


def test_run_once_voices_the_most_urgent_chapter_end_to_end(tmp_path):
    s, conn, (a, b), c = setup(tmp_path)
    engine = FakeEngine()
    assert run_once(VoiceClient(c), engine) == 1
    assert engine.calls[0].startswith("第2章,甲2。")  # 甲读到第 2 章:先配它
    hq = repo.get_audio(conn, repo.get_chapter(conn, a, 2)["id"], "hq")
    assert hq and (s.audio_dir / hq["path"]).is_file()
    assert c.get("/api/voice/status").json()["worker_online"] is True


def test_drains_the_queue_then_reports_idle(tmp_path):
    s, conn, books, c = setup(tmp_path)
    client, engine = VoiceClient(c), FakeEngine()
    assert sum(run_once(client, engine) for _ in range(6)) == 5  # 两本书共 5 章
    assert run_once(client, engine) == 0
    assert c.get("/api/voice/status").json()["pending"] == 0


def test_log_lines_the_launcher_reads(tmp_path, caplog):
    """启动器窗口靠日志里的"开始配/配好"显示"正在配第几章、已配几章";措辞变了窗口就不准了。"""
    s, conn, books, c = setup(tmp_path)
    with caplog.at_level("INFO", logger="huaben_voice"):
        run_once(VoiceClient(c), FakeEngine())
    msgs = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("开始配 ") and "第 2 章" in m for m in msgs)
    assert any("配好" in m for m in msgs)


def test_token_is_sent(tmp_path):
    s, conn, books, c = setup(tmp_path, voice_worker_token="t0k")
    with pytest.raises(ServerError, match="401"):
        VoiceClient(c).fetch_jobs()
    assert run_once(VoiceClient(c, token="t0k"), FakeEngine()) == 1


def test_errors_back_off_and_never_exit():
    class Flaky:
        def __init__(self):
            self.n = 0

        def fetch_jobs(self, limit=1, voice=""):
            self.n += 1
            raise ServerError("服务器重启中")

    sleeps, client = [], Flaky()
    run_forever(client, FakeEngine(), idle_s=30, max_backoff_s=100, sleep=sleeps.append,
                should_stop=lambda: client.n >= 4)
    assert sleeps == [30, 60, 100, 100]  # 指数退避、封顶;一直在重试,不退出


def test_unknown_engine_is_a_clear_error():
    with pytest.raises(ValueError, match="可用"):
        create_engine("nope")


def test_kokoro_segments_keep_every_char_and_respect_limit():
    from huaben_voice.kokoro_zh import segments
    text = "第一段。很短。\n\n" + "长句子没有标点" * 30 + "。结尾!\n最后一段"
    paras = segments(text, max_chars=40)
    assert len(paras) == 3                                  # 空行不算段
    flat = [s for p in paras for s in p]
    assert all(len(s) <= 40 for s in flat)
    assert "".join(flat) == text.replace("\n", "")          # 不丢字、不重复
    assert paras[0] == ["第一段。很短。"]                     # 短句拼成一段


def test_qwen3_engine_clones_a_named_reference_voice(tmp_path):
    """克隆模式:音色名 = voices/ 里的一段参考音 + 它的文字;名字不存在时说清楚有哪些。导入不需要 torch(惰性)。"""
    from huaben_voice.engines import ENGINES
    from huaben_voice.qwen3_zh import VOICES_DIR, reference
    assert "qwen3-zh" in ENGINES
    assert {"女声", "男声"} <= {p.stem for p in VOICES_DIR.glob("*.wav")}  # 交付的两个音色都在
    wav, text = reference("女声")
    assert wav.is_file() and text
    with pytest.raises(ValueError, match="现有"):
        reference("不存在", tmp_path)


def test_runaway_generation_is_capped_and_detected():
    """正式配音实测:一段不到 200 字生成了 161 秒(顶到默认 2048 token 上限)。上限按字数给,超长判失控重来。"""
    from huaben_voice.qwen3_zh import runaway, token_cap
    seg = "字" * 200                      # 预计 40 秒
    assert token_cap(seg) == 1200         # 40 秒 × 2.5 × 12 token/秒,远低于默认 2048
    assert token_cap("好。") == 72        # 很短的段至少给 6 秒
    assert not runaway(seg, 45) and runaway(seg, 161) and runaway(seg, 99)  # 99 秒 ≈ 顶到上限


def test_voice_id_carries_the_cut_version_for_qwen():
    from huaben_voice.__main__ import voice_id
    from huaben_voice.chunks import CUT_VERSION
    assert voice_id("qwen3-zh", "女声") == f"qwen3-zh:女声:{CUT_VERSION}"
    assert voice_id("kokoro-zh", "zf_001") == "kokoro-zh:zf_001"
    assert voice_id("qwen3-zh", "女声", "慢一点").endswith(f":{CUT_VERSION}")
    assert voice_id("qwen3-zh", "女声", "慢一点") != voice_id("qwen3-zh", "女声")
