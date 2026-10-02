"""没有可用模型时,正在等文字的书要看得见原因(路线 23)。"""
from types import SimpleNamespace

from huaben import repo
from huaben.config import Settings
from huaben.db import connect
from huaben.llm_fake import FakeLLM
from huaben.worker import Backoff, Worker
from test_worker import CHAPTER, PLAN


def setup_books(tmp_path):
    s = Settings(openrouter_api_key="", chapter_words=1, data_dir=tmp_path, buffer_chapters=1,
                 worker_enabled=False, _env_file=None)
    conn = connect(s.db_path)
    waiting = repo.create_book(conn, "等第一章")
    repo.update_book(conn, waiting, status="serializing")
    full = repo.create_book(conn, "缓冲已满")
    repo.update_book(conn, full, status="serializing")
    vid = repo.create_volume(conn, full, 1, status="active")
    cid = repo.create_chapter(conn, full, vid, 1, title="T")
    repo.update_chapter(conn, cid, body="b", summary="s", status="accepted")
    draft = repo.create_book(conn, "开书中")
    return s, conn, waiting, full, draft


def test_missing_key_is_shown_on_books_waiting_for_text_only(tmp_path):
    s, conn, waiting, full, draft = setup_books(tmp_path)
    Worker(SimpleNamespace(settings=s, llm=None, tts=None), 60, Backoff(60, 600)).tick()
    assert "还没有配置模型密钥" in repo.get_book(conn, waiting)["gen_error"]  # 人话 + 该做什么
    assert repo.get_book(conn, full)["gen_error"] == ""   # 暂不受影响,不打扰
    assert repo.get_book(conn, draft)["gen_error"] == ""  # 开书中的书不归后台管


def test_message_clears_once_model_is_available(tmp_path):
    s, conn, waiting, _, _ = setup_books(tmp_path)
    state = SimpleNamespace(settings=s, llm=None, tts=None)
    w = Worker(state, 60, Backoff(60, 600))
    w.tick()
    assert repo.get_book(conn, waiting)["gen_error"]
    state.llm = FakeLLM([PLAN] + CHAPTER)  # 配好密钥并重启后,等价于有了可用的客户端
    assert w.tick()[waiting].generated == 1
    assert repo.get_book(conn, waiting)["gen_error"] == ""
