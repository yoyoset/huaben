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


def test_token_is_sent(tmp_path):
    s, conn, books, c = setup(tmp_path, voice_worker_token="t0k")
    with pytest.raises(ServerError, match="401"):
        VoiceClient(c).fetch_jobs()
    assert run_once(VoiceClient(c, token="t0k"), FakeEngine()) == 1


def test_errors_back_off_and_never_exit():
    class Flaky:
        def __init__(self):
            self.n = 0

        def fetch_jobs(self, limit=1):
            self.n += 1
            raise ServerError("服务器重启中")

    sleeps, client = [], Flaky()
    run_forever(client, FakeEngine(), idle_s=30, max_backoff_s=100, sleep=sleeps.append,
                should_stop=lambda: client.n >= 4)
    assert sleeps == [30, 60, 100, 100]  # 指数退避、封顶;一直在重试,不退出


def test_unknown_engine_is_a_clear_error():
    with pytest.raises(ValueError, match="可用"):
        create_engine("nope")
