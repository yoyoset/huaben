"""结构化日志:每行带上书/章上下文;关键步骤各一行;重复告警不刷屏。"""
import json
import logging
from types import SimpleNamespace

import pytest

from huaben import repo
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.logs import ContextFilter, _ctx, log_context, render_ctx
from huaben.scheduler import top_up
from huaben.worker import Backoff, Worker

PLAN = json.dumps({"goal": "g", "beats": ["a"], "plant": [], "resolve": [], "target_chapters": 30})
OUTLINE = json.dumps({"title": "夜巡", "outline": "事", "characters": [], "foreshadows": [],
                      "planned_reversals": [], "hook": "钩"}, ensure_ascii=False)
LEDGER = json.dumps({"summary": "s", "characters": [], "foreshadows_new": [], "foreshadows_update": [],
                     "facts": [], "contradictions": []})


@pytest.fixture
def lines():
    """收集带上下文的日志行(与线上同一格式)。"""
    out: list[str] = []

    class H(logging.Handler):
        def emit(self, record):
            out.append(f"{record.levelname} {record.name}{record.ctx} {record.getMessage()}")

    h = H()
    h.addFilter(ContextFilter())
    root = logging.getLogger()
    root.addHandler(h)
    old = root.level
    root.setLevel(logging.INFO)
    yield out
    root.removeHandler(h)
    root.setLevel(old)


def test_context_nesting_and_restore():
    assert render_ctx({}) == ""
    with log_context(book=3):
        with log_context(chapter=12):
            assert render_ctx(_ctx.get()) == " [book=3 ch=12]"
        assert render_ctx(_ctx.get()) == " [book=3]"


def test_generation_lines_carry_book_and_chapter(conn, lines):
    bid = repo.create_book(conn, "x")
    repo.update_book(conn, bid, status="serializing")
    s = Settings(openrouter_api_key="x", chapter_words=1, buffer_chapters=1, _env_file=None)
    top_up(conn, FakeLLM([PLAN, OUTLINE, "正文", LEDGER]), s, bid)
    text = "\n".join(lines)
    assert f"[book={bid}] step=volume_plan ok=true" in text            # 卷级步骤:只有书
    assert f"[book={bid} ch=1] step=write ok=true" in text              # 章级步骤:书 + 章
    assert f"[book={bid} ch=1] chapter=accepted attempt=1 title=夜巡" in text
    assert f"[book={bid}] top_up generated=1" in text


def test_rejections_are_logged_as_warnings(conn, lines):
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, status="active")
    repo.update_book(conn, bid, status="serializing")
    bad = json.dumps({"summary": "s", "contradictions": [{"what": "死人复活", "planned": False}]}, ensure_ascii=False)
    s = Settings(openrouter_api_key="x", chapter_words=1, buffer_chapters=1, _env_file=None)
    top_up(conn, FakeLLM([OUTLINE, "稿一", bad, "稿二", LEDGER]), s, bid)
    assert any(line.startswith("WARNING") and "check=reject contradiction: 死人复活" in line for line in lines)


def test_missing_key_warning_logged_once(tmp_path, lines):
    s = Settings(openrouter_api_key="", data_dir=tmp_path, worker_enabled=False, _env_file=None)
    w = Worker(SimpleNamespace(settings=s, llm=None, tts=None), 60, Backoff(60, 600))
    for _ in range(3):
        w.tick()
    assert sum("后台补货暂停" in line for line in lines) == 1
