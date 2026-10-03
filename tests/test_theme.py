"""故事的主题与核心谜团(路线 69):OP/火影/死神的超长线最后都指向一个"这本书在讲什么"的核心。"""
import json

from huaben import repo
from huaben.config import Settings
from huaben.context import load_context
from huaben.llm_fake import FakeLLM
from huaben.opening.service import finalize_book
from huaben.pipeline.volume_prompts import plan_messages
from huaben.render import render_bible
from huaben.theme import advance_rule, normalize, render


def test_normalize_and_render():
    assert normalize("自由的代价", "世界的真相") == ("自由的代价", "世界的真相")
    assert render("", "") == ""
    out = render("羁绊与仇恨的循环", "面具下到底是谁")
    assert "主题" in out and "核心谜团" in out and "面具下到底是谁" in out
    assert "每一卷都要朝它推进一步" in out
    assert advance_rule(False) == "" and "推进一步" in advance_rule(True)


def test_render_bible_puts_theme_first():
    bible = {"theme": "自由的代价", "central_mystery": "空白的一百年", "world": "海与岛",
             "characters": [{"name": "路", "role": "主角", "traits": "直"}]}
    out = render_bible(bible)
    assert out.startswith("【故事的主题与核心谜团") and "空白的一百年" in out
    assert "【世界观与规则】" in out


def test_finalize_persists_theme_and_mystery(conn):
    S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)
    bid = repo.create_book(conn, "未命名")
    repo.add_message(conn, bid, "user", "我要一个海贼那样的故事")
    bible = json.dumps({
        "title": "航路", "genre": "冒险", "synopsis": "少年出海。", "theme": "自由的代价",
        "central_mystery": "空白的一百年真相", "world": "海与岛",
        "characters": [{"name": "路", "role": "主角", "traits": "直"}], "core_characters": ["路"],
        "style_fingerprint": "热血", "taboos": [],
    }, ensure_ascii=False)
    plan = json.dumps({"goal": "出海", "beats": ["a"], "plant": [], "resolve": [], "target_chapters": 30}, ensure_ascii=False)
    finalize_book(conn, FakeLLM([bible, plan]), S, bid)
    b = repo.get_bible(conn, bid)
    assert b["theme"] == "自由的代价" and b["central_mystery"] == "空白的一百年真相"


def test_volume_plan_asks_to_advance_the_central_mystery(conn):
    bid = repo.create_book(conn, "书")
    repo.save_bible(conn, bid, theme="自由的代价", central_mystery="空白的一百年")
    repo.create_volume(conn, bid, 1, status="active")
    user = plan_messages(load_context(conn, bid), 2)[1]["content"]
    assert "朝【故事的主题与核心谜团】推进一步" in user
    # 没写主题的书:不加这句
    bid2 = repo.create_book(conn, "无主题")
    repo.create_volume(conn, bid2, 1, status="active")
    assert "朝【故事的主题与核心谜团】推进一步" not in plan_messages(load_context(conn, bid2), 2)[1]["content"]
