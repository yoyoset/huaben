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
    "characters": [{"name": "沈照", "role": "主角", "traits": "腹黑",
                    "signature": {"name": "听风耳", "rule": "听见三里内的私语", "stage": "初开", "next": "辨心音"}},
                   {"name": "阿蘅", "role": "药师", "traits": "冷"}],
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
    # 开书时定的招牌能力要落到账本(路线 58):否则章纲/正文看不到,模型又会临时给万能能力
    assert chars["沈照"]["signature"]["name"] == "听风耳" and chars["沈照"]["signature"]["stage"] == "初开"
    assert chars["阿蘅"]["signature"] == {}
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


def test_retry_after_more_conversation_reextracts_bible(conn, book):
    """开书失败(卷规划失败)后用户又补充了设定:重试时必须按完整对话重新整理圣经,旧人物不残留。"""
    repo.add_message(conn, book, "user", "古代恐怖")
    with pytest.raises(ChapterFailed):
        finalize_book(conn, FakeLLM([BIBLE, "坏", "坏"]), S, book)
    repo.add_message(conn, book, "user", "主角换成女的,叫阿蘅")
    new_bible = json.dumps({
        "title": "夜行录", "genre": "古代恐怖", "synopsis": "女夜巡人的故事。", "world": "灵气枯竭的王朝",
        "characters": [{"name": "阿蘅", "role": "主角", "traits": "冷"}], "core_characters": ["阿蘅"],
        "style_fingerprint": "短句", "taboos": [],
    }, ensure_ascii=False)
    llm = FakeLLM([new_bible, PLAN])
    out = finalize_book(conn, llm, S, book)
    assert "主角换成女的" in llm.calls[0][-1]["content"]           # 新补充的话进了整理
    assert out["synopsis"] == "女夜巡人的故事。"
    assert [c["name"] for c in repo.list_characters(conn, book)] == ["阿蘅"]  # 旧圣经的人物没有残留
    assert repo.get_bible(conn, book)["extracted_msgs"] == 2


def test_failed_turn_stores_nothing_so_resend_is_not_duplicated(conn, book):
    from huaben.llm import LLMError
    with pytest.raises(LLMError):
        opening_turn(conn, FakeLLM([LLMError("down", kind="server")]), book, "古代恐怖")
    assert repo.list_messages(conn, book) == []  # 失败:不留悬空的用户消息
    llm = FakeLLM([guide("好")])
    opening_turn(conn, llm, book, "古代恐怖")    # 重发
    assert [m["content"] for m in repo.list_messages(conn, book)] == ["古代恐怖", "好"]
    assert llm.calls[0][-1] == {"role": "user", "content": "古代恐怖"}  # 新消息仍然在发给模型的末尾
