"""同一本书的开书请求不能并发(路线 21)。

复现方式:第一个开书请求卡在模型调用里(约 1 分钟的真实场景),这时再发第二个。
"""
import threading

import pytest
from fastapi.testclient import TestClient

from huaben import repo
from huaben.api.app import create_app
from huaben.config import Settings
from huaben.db import connect
from huaben.llm import LLMResult
from huaben.llm_fake import FakeLLM
from huaben.opening.service import OpeningBusy, finalize_book, opening_turn
from test_opening import BIBLE, PLAN


class GatedLLM(FakeLLM):
    """第一次调用停在闸门前,直到测试放行——模拟"开书进行中"。"""

    def __init__(self, replies):
        super().__init__(replies)
        self.entered, self.gate = threading.Event(), threading.Event()

    def chat(self, messages, **kw) -> LLMResult:
        if not self.entered.is_set():
            self.entered.set()
            self.gate.wait(5)
        return super().chat(messages, **kw)


@pytest.fixture
def setup(tmp_path):
    s = Settings(openrouter_api_key="x", chapter_words=1, data_dir=tmp_path, worker_enabled=False, _env_file=None)
    conn = connect(s.db_path, check_same_thread=False)
    bid = repo.create_book(conn, "未命名")
    repo.add_message(conn, bid, "user", "我想看古代恐怖")
    return s, conn, bid


def start_first_finalize(s, bid, llm):
    out = {}
    t = threading.Thread(target=lambda: out.update(book=finalize_book(
        connect(s.db_path, check_same_thread=False), llm, s, bid)))
    t.start()
    assert llm.entered.wait(5)
    return t, out


def test_second_finalize_and_messages_are_rejected_while_first_runs(setup):
    s, conn, bid = setup
    llm = GatedLLM([BIBLE, PLAN])
    t, out = start_first_finalize(s, bid, llm)
    with pytest.raises(OpeningBusy):
        finalize_book(conn, FakeLLM([]), s, bid)           # 不重复花钱、不撞卷表唯一约束
    with pytest.raises(OpeningBusy):
        opening_turn(conn, FakeLLM([]), bid, "再补一句")     # 定稿期间补的话不会漏进圣经
    llm.gate.set()
    t.join(5)
    assert out["book"]["status"] == "serializing"
    assert len(repo.list_volumes(conn, bid)) == 1
    assert len(llm.calls) == 2  # 圣经 + 第 1 卷规划,各只一次


def test_api_answers_409_so_the_page_waits_instead_of_failing(setup):
    s, conn, bid = setup
    llm = GatedLLM([BIBLE, PLAN])
    app = create_app(s, llm=FakeLLM([]))
    t, _ = start_first_finalize(s, bid, llm)
    r = TestClient(app).post(f"/api/books/{bid}/finalize")
    llm.gate.set()
    t.join(5)
    assert r.status_code == 409 and "正在开书" in r.json()["detail"]


def test_lock_is_released_after_failure(setup):
    s, conn, bid = setup
    with pytest.raises(Exception):
        finalize_book(conn, FakeLLM(["坏", "坏"]), s, bid)  # 圣经两次都解析不了
    assert finalize_book(conn, FakeLLM([BIBLE, PLAN]), s, bid)["status"] == "serializing"
