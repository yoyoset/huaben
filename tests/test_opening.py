import json

import pytest

from huaben import repo
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.opening.parsing import parse_bible, parse_guide
from huaben.opening.service import (OpeningError, finalize_book, opening_turn, style_samples_from,
                                    transcript)
from huaben.pipeline.errors import ChapterFailed
from huaben.pipeline.parsing import ParseError

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)

BIBLE = json.dumps({
    "title": "夜行录", "genre": "古代恐怖", "synopsis": "少年夜巡人的故事。", "world": "灵气枯竭的王朝",
    "characters": [{"name": "沈照", "role": "主角", "traits": "腹黑"}, {"name": "阿蘅", "role": "药师", "traits": "冷"}],
    "core_characters": ["沈照"], "style_fingerprint": "短句,冷幽默", "taboos": ["现代梗"],
}, ensure_ascii=False)
PLAN = json.dumps({"goal": "入门", "beats": ["a"], "plant": [], "resolve": [], "target_chapters": 30}, ensure_ascii=False)


def guide(reply="想要什么题材?", ready=False):
    return json.dumps({"reply": reply, "ready": ready}, ensure_ascii=False)


@pytest.fixture
def book(conn):
    return repo.create_book(conn, "未命名")


def test_turn_persists_both_sides_and_passes_history(conn, book):
    llm = FakeLLM([guide("喜欢哪类?"), guide("有雷点吗?", True)])
    r1 = opening_turn(conn, llm, book, "我想看古代恐怖")
    assert r1 == {"reply": "喜欢哪类?", "ready": False}
    r2 = opening_turn(conn, llm, book, "不要现代梗")
    assert r2["ready"] is True
    sent = llm.calls[1]
    assert [m["role"] for m in sent] == ["system", "user", "assistant", "user"]
    assert repo.list_messages(conn, book)[-1] == {"role": "assistant", "content": "有雷点吗?"}


def test_turn_tolerates_plain_text_reply(conn, book):
    r = opening_turn(conn, FakeLLM(["好的,那你喜欢什么风格?"]), book, "你好")
    assert r == {"reply": "好的,那你喜欢什么风格?", "ready": False}


def test_turn_rejects_bad_state(conn, book):
    with pytest.raises(OpeningError):
        opening_turn(conn, FakeLLM([]), book, "   ")
    with pytest.raises(OpeningError):
        opening_turn(conn, FakeLLM([]), 999, "x")
    repo.update_book(conn, book, status="serializing")
    with pytest.raises(OpeningError):
        opening_turn(conn, FakeLLM([]), book, "x")


def test_style_samples_are_verbatim_user_text_only():
    long_text = "夜很长,风很冷。" * 40
    msgs = [{"role": "user", "content": "短消息"}, {"role": "assistant", "content": "长" * 500},
            {"role": "user", "content": long_text}, {"role": "user", "content": "又一段。" * 100}]
    out = style_samples_from(msgs)
    assert out[0] == long_text[:1500] and len(out) == 2  # 向导的长回复不算样章
    assert transcript(msgs[:2]) == "读者:短消息\n向导:" + "长" * 500


def test_parsers():
    assert parse_guide(guide("hi", True)) == {"reply": "hi", "ready": True}
    assert parse_guide('{"reply":"x","ready":"yes"}')["ready"] is False  # 只认布尔 true
    with pytest.raises(ParseError):
        parse_guide("   ")
    with pytest.raises(ParseError):
        parse_bible(json.dumps({"title": "t"}))


def test_finalize_builds_bible_ledger_volume_and_goes_live(conn, book):
    sample = "夜很长,风很冷。" * 40
    repo.add_message(conn, book, "user", "古代恐怖,不要现代梗")
    repo.add_message(conn, book, "user", sample)
    out = finalize_book(conn, FakeLLM([BIBLE, PLAN]), S, book)
    assert out["status"] == "serializing" and out["title"] == "夜行录" and out["synopsis"] == "少年夜巡人的故事。"
    bible = repo.get_bible(conn, book)
    assert bible["world"] == "灵气枯竭的王朝" and bible["taboos"] == ["现代梗"]
    assert bible["style_samples"] == [sample]
    chars = {c["name"]: c for c in repo.list_characters(conn, book)}
    assert chars["沈照"]["core"] is True and chars["阿蘅"]["core"] is False
    assert repo.active_volume(conn, book)["goal"] == "入门"


def test_finalize_needs_conversation_and_is_once_only(conn, book):
    with pytest.raises(OpeningError, match="对话"):
        finalize_book(conn, FakeLLM([]), S, book)
    repo.add_message(conn, book, "user", "古代恐怖")
    finalize_book(conn, FakeLLM([BIBLE, PLAN]), S, book)
    with pytest.raises(OpeningError, match="已经开书"):
        finalize_book(conn, FakeLLM([]), S, book)


def test_finalize_retry_after_volume_failure_skips_bible(conn, book):
    repo.add_message(conn, book, "user", "古代恐怖")
    with pytest.raises(ChapterFailed):
        finalize_book(conn, FakeLLM([BIBLE, "坏", "坏"]), S, book)  # 圣经成功,卷规划失败
    assert repo.get_book(conn, book)["status"] == "drafting"  # 没有"半开"的连载书
    llm = FakeLLM([PLAN])  # 重试只需再规划卷,不重复抽圣经
    assert finalize_book(conn, llm, S, book)["status"] == "serializing" and len(llm.calls) == 1


def test_finalize_bad_bible_fails_cleanly(conn, book):
    repo.add_message(conn, book, "user", "古代恐怖")
    with pytest.raises(ChapterFailed):
        finalize_book(conn, FakeLLM(["不是json", '{"title":"x"}']), S, book)
    assert repo.get_bible(conn, book)["world"] == "" and repo.get_book(conn, book)["status"] == "drafting"
