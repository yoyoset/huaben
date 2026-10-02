"""正文质量底线:拦"明显不是一章小说"的稿子,能清理的自动清理。"""
import json

from huaben import repo
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.pipeline.chapter import generate_chapter
from huaben.pipeline.draft_check import clean_draft, content_length, draft_problems, looks_like_refusal

GOOD = "\n".join(f"第{i}段。沈照提灯走过后山,井边的敲击声一下又一下,像有人在下面数着他的步子。" for i in range(40))


def test_good_draft_passes():
    assert draft_problems(GOOD, 1000) == []


def test_clean_strips_heading_and_trailer_only():
    raw = "第十二章 井底\n\n" + GOOD + "\n(本章完)"
    assert clean_draft(raw) == GOOD
    assert clean_draft("# 井底\n" + GOOD).startswith("第0段")
    assert clean_draft("标题:井底\n" + GOOD).startswith("第0段")


def test_clean_keeps_sentence_that_looks_like_heading():
    assert clean_draft("第三章节的内容。他想。\n后文") == "第三章节的内容。他想。\n后文"  # 有句末标点:是正文
    assert clean_draft("第一章") == "第一章"  # 只有这一行:不清空,交给篇幅检查


def test_too_short():
    p = draft_problems("沈照醒了。", 2500)
    assert p and "篇幅不足" in p[0]


def test_refusal_detected():
    text = "抱歉,我无法继续创作这个情节。" + GOOD
    assert any("不是小说正文" in p for p in draft_problems(text, 100))


def test_refusal_variants_still_caught():
    for head in ("  很抱歉,这个请求我不能完成。", "I'm sorry, but I can't write that.",
                 "以下是说明:作为一个AI语言模型,我需要提醒你……", "作为人工智能,我不能生成这类内容。"):
        assert looks_like_refusal(head + GOOD), head


def test_dialogue_with_apology_or_refusal_is_a_normal_chapter():
    """实测曾误伤:前 300 字里的人物台词含"抱歉/我不能提供",整章被判"不是小说正文"。"""
    for head in ("“抱歉,我来晚了。”沈照推门而入,雨水顺着斗笠往下淌。\n",
                 "老掌柜摇头:“我不能提供这种药,官府查得紧。”\n",
                 "他抱歉地笑了笑,没有接话。\n",
                 "「作为一个AI,我只听主人的。」铁傀儡说。\n"):  # 故事里的 AI 角色说话
        assert not looks_like_refusal(head + GOOD), head
        assert draft_problems(head + GOOD, 1000) == [], head


def test_missing_punctuation_in_tail_detected():
    """前身实测:惩罚参数非 0 时,长章后半段标点全部消失、句子粘成一片。"""
    text = GOOD + "\n" + "他走过去看见井里有一盏灯灯下有一个人那个人抬头看他笑了一下又低头" * 20
    assert any("标点缺失" in p for p in draft_problems(text, 100))


def test_repeated_paragraphs_detected():
    para = "井边的敲击声一下又一下,像有人在下面数着他的步子。"
    text = GOOD + "\n" + "\n".join([para] * 4)
    assert any("重复" in p for p in draft_problems(text, 100))


def test_content_length_ignores_whitespace():
    assert content_length("甲 乙\n丙\t") == 3


def test_pipeline_rewrites_bad_draft_without_spending_on_ledger(conn):
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, status="active")
    outline = json.dumps({"title": "T", "outline": "事", "characters": [], "foreshadows": [],
                          "planned_reversals": [], "hook": "钩"}, ensure_ascii=False)
    ledger = json.dumps({"summary": "s", "characters": [], "foreshadows_new": [], "foreshadows_update": [],
                         "facts": [], "contradictions": []})
    llm = FakeLLM([outline, "抱歉,我无法写这个。", "第一章 夜巡\n" + GOOD, ledger])
    ch = generate_chapter(conn, llm, Settings(openrouter_api_key="x", chapter_words=1000, _env_file=None), bid)
    assert ch["attempts"] == 2 and ch["body"] == GOOD  # 拒答被打回;第二稿的标题行被清掉
    assert "不是小说正文" in llm.calls[2][-1]["content"]  # 打回理由交给了重写
    assert len(llm.calls) == 4  # 拒答那稿没有调用入账
