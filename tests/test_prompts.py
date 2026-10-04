"""prompt 组装:编辑的计划必须完整交到作者/核对者手上。"""
import pytest

from huaben import repo
from huaben.context import load_context
from huaben.pipeline.prompts import ledger_messages, outline_scope, work_order, write_messages


def outline(**kw):
    d = {"title": "井底", "outline": "沈照下井", "characters": ["沈照"], "foreshadows": [],
         "planned_reversals": [], "hook": "灯灭了"}
    d.update(kw)
    return d


@pytest.fixture
def ctx(conn):
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, goal="g", status="active")
    repo.upsert_character(conn, bid, "沈照", core=True)
    return load_context(conn, bid)


def test_work_order_without_reversal():
    w = work_order(3, outline())
    assert "第 3 章《井底》" in w and "沈照下井" in w and "结尾钩子:灯灭了" in w
    assert "反转" not in w


def test_planned_reversal_reaches_the_writer(ctx):
    o = outline(planned_reversals=["老道没死,是假死脱身"])
    user = write_messages(ctx, o, 2500)[-1]["content"]
    assert "老道没死,是假死脱身" in user                    # 计划交到了作者手上
    assert "除工单列出的有意反转外,严格遵守账本" in user      # 硬约束给反转留了口子,指令不再自相矛盾


def test_no_reversal_keeps_strict_rule(ctx):
    user = write_messages(ctx, outline(), 2500)[-1]["content"]
    assert "2. 严格遵守账本里的人物现状与世界事实" in user and "有意反转" not in user


def test_ledger_check_still_sees_reversals(ctx):
    user = ledger_messages(ctx, outline(planned_reversals=["假死"]), "正文")[-1]["content"]
    assert "假死" in user


def test_outline_scope_separates_words():
    assert outline_scope(outline(outline="井", characters=["阿蘅", "老道"])) == "井 阿蘅 老道"


def test_ledger_check_sees_characters_the_writer_brought_in(conn):
    """章纲没提、作者自己写进正文的已死配角:核对 prompt 里必须有他的"已死亡"状态,否则复活查不出。"""
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, goal="g", status="active")
    repo.upsert_character(conn, bid, "老道", alive=False)
    c = load_context(conn, bid)
    o = outline()  # 章纲只提沈照
    assert "老道" not in write_messages(c, o, 2500)[-1]["content"]          # 写作时不占 prompt
    user = ledger_messages(c, o, "沈照回头,看见老道正站在井边冲他笑。")[-1]["content"]
    assert "老道(已死亡)" in user.split("【本章章纲】")[0]                   # 核对时账本里有他的状态


def _ctx_at(conn, done: int, target: int = 10, beats=("起", "承", "转", "合", "收")):
    from huaben.context import StoryContext
    vol = {"id": 1, "idx": 2, "goal": "下山", "beats": list(beats), "plant": [], "resolve": [], "target_chapters": target}
    return StoryContext(book={"synopsis": ""}, bible={}, volume=vol, past_volume_summaries=[],
                        volume_chapter_summaries=[], recent=[], characters=[], foreshadows=[], facts=[],
                        next_idx=11 + done, volume_done=done)


@pytest.mark.parametrize("done,expect", [
    (0, "第 1/5 个节拍「起」"),
    (4, "第 3/5 个节拍「转」"),
    (7, "收尾阶段(本章之后只剩 2 章)"),
    (9, "本章是本卷最后一章"),
])
def test_pacing_follows_volume_progress(conn, done, expect):
    from huaben.pipeline.prompts import outline_messages, pacing_rule
    c = _ctx_at(conn, done)
    assert expect in pacing_rule(c)
    assert expect in outline_messages(c)[-1]["content"]


def test_writer_also_sees_volume_progress(conn):
    from huaben.render import render_memory
    out = render_memory(_ctx_at(conn, 9))
    assert "本卷进度:即将写本卷第 10/10 章(写完本章后本卷还剩 0 章)" in out


def test_load_context_counts_volume_progress(conn):
    bid = repo.create_book(conn, "x")
    vid = repo.create_volume(conn, bid, 1, status="active", target_chapters=10)
    for i in (1, 2, 3):
        cid = repo.create_chapter(conn, bid, vid, i)
        repo.update_chapter(conn, cid, status="accepted", summary="s")
    assert load_context(conn, bid).volume_done == 3


def test_named_foreshadows_reach_writer_and_ledger(conn):
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, goal="g", status="active")
    fid = repo.add_foreshadow(conn, bid, 2, "玉佩发烫")
    c = load_context(conn, bid)
    o = outline(foreshadows=[fid, 999])
    w = write_messages(c, o, 2500)[-1]["content"]
    assert f"本章要推进或回收的伏笔(要在情节里落到实处):\n- #{fid} 玉佩发烫(第2章埋)" in w
    assert "#999" not in w.split("【本章工单】")[1]  # 不存在的编号不进工单
    assert f"章纲点名要推进的伏笔:#{fid}、#999" in ledger_messages(c, o, "正文")[-1]["content"]


def test_unfollowed_thread_is_logged(conn):
    import json
    from huaben.config import Settings
    from huaben.llm_fake import FakeLLM
    from huaben.pipeline.chapter import generate_chapter
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, goal="g", status="active")
    fid = repo.add_foreshadow(conn, bid, 0, "玉佩")
    o = json.dumps(outline(foreshadows=[fid]), ensure_ascii=False)
    led = json.dumps({"summary": "s", "characters": [], "foreshadows_new": [], "foreshadows_update": [],
                      "facts": [], "contradictions": []})
    generate_chapter(conn, FakeLLM([o, "正文", led]), Settings(openrouter_api_key="x", chapter_words=1,
                                                                 _env_file=None), bid)
    note = conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE '%未见推进%'").fetchone()[0]
    assert f"#{fid}" in note


def test_new_character_profile_is_kept_and_rendered(conn):
    """中途登场的配角:首次入账记下人设,之后入账没给/给空也不丢;出场时人设随现状进 prompt。"""
    from huaben.pipeline.ledger_apply import merge_character
    from huaben.pipeline.normalize import normalize_ledger
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, goal="g", status="active")
    first = normalize_ledger({"summary": "s", "characters": [{"name": "老道", "profile": "后山守井人,话少,爱用反问"}]})
    repo.upsert_character(conn, bid, "老道", **merge_character(None, first["characters"][0]))
    later = normalize_ledger({"summary": "s", "characters": [{"name": "老道", "profile": "", "location": "井边"}]})
    old = repo.list_characters(conn, bid)[0]
    repo.upsert_character(conn, bid, "老道", **merge_character(old, later["characters"][0]))
    c = repo.list_characters(conn, bid)[0]
    assert c["profile"] == "后山守井人,话少,爱用反问" and c["location"] == "井边"
    w = write_messages(load_context(conn, bid), outline(outline="老道出现"), 2500)[-1]["content"]
    assert "老道(存活);人设:后山守井人,话少,爱用反问" in w


def test_bible_characters_do_not_repeat_profile(conn):
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, goal="g", status="active")
    repo.save_bible(conn, bid, characters=[{"name": "沈照", "role": "主角", "traits": "腹黑"}])
    repo.upsert_character(conn, bid, "沈照", core=True, profile="主角 腹黑")
    w = write_messages(load_context(conn, bid), outline(), 2500)[-1]["content"]
    assert "沈照(存活)" in w and "人设:主角 腹黑" not in w  # 人物卡里已有,账本只带现状


def test_must_and_should_are_groups_without_blank_lines(ctx):
    """关思考的模型分不清"底线"和"习惯":【必须】里 1~4 连续编号,【尽量做到】是清单,中间不隔空行。"""
    block = write_messages(ctx, outline(), 2500)[-1]["content"].split(f"现在写第 {ctx.next_idx} 章正文")[1]
    pos = [block.index(f"{i}.") for i in range(1, 5)]
    assert pos == sorted(pos)                       # 1. 到 4. 依次出现,没有跳号
    assert "【必须】" in block and "【尽量做到" in block
    assert "\n\n" not in block                       # 没有连续两个空行


def test_write_messages_groups_must_and_should(ctx):
    """T030:"必须"的底线排在前面、"尽量"的写法习惯排在后面,模型才分得出主次。"""
    from huaben.pipeline.rules import SIGNATURE_RULE, SPEECH_RULE
    user = write_messages(ctx, outline(), 2500)[-1]["content"]
    assert "硬性要求" not in user
    must_at, should_at = user.index("【必须】"), user.index("【尽量做到")
    assert must_at < should_at
    assert "只输出正文" in user[must_at:should_at]
    assert SIGNATURE_RULE in user[should_at:] and SPEECH_RULE in user[should_at:]


def test_no_opening_block_or_double_blank_after_the_first_three_chapters(conn):
    later = write_messages(_ctx_at(conn, 0), outline(), 2500)[-1]["content"]  # next_idx = 11
    block = later.split("现在写第 11 章正文")[1]
    assert "【开篇要求】" not in block and "\n\n" not in block


def test_title_rule_says_this_book():
    from huaben.pipeline.rules import title_rule
    assert title_rule(["甲"]).startswith("本书已有章节标题")


def test_work_order_renders_grip_and_loose_ending():
    w = work_order(3, outline(grip="松", ending="他站起来了。"))
    assert "放开写" in w and "意思到了就行" in w


def test_ledger_check_includes_must_only_if_present(ctx):
    assert "【本章不能错的】" in ledger_messages(ctx, outline(must=["厉九不出手"]), "正文")[-1]["content"]
    assert "【本章不能错的】" not in ledger_messages(ctx, outline(), "正文")[-1]["content"]
