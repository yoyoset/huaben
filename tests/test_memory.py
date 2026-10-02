import pytest

from huaben import repo
from huaben.context import load_context, select_ledger
from huaben.render import recent_text, render_bible, render_memory, render_style_samples


@pytest.fixture
def book(conn):
    """两卷:第 1 卷已封,第 2 卷进行中,已有 5 章(1~2 属于卷 1,3~5 属于卷 2)。"""
    bid = repo.create_book(conn, "诡仙")
    repo.update_book(conn, bid, synopsis="少年入宗门,发现宗门是个笼子。")
    v1 = repo.create_volume(conn, bid, 1, goal="入门")
    v2 = repo.create_volume(conn, bid, 2, goal="下山", beats=["离宗", "遇险"], plant=["玉佩"], resolve=["井声"], status="active")
    repo.seal_volume(conn, v1, "主角入了太玄宗。")
    for i in range(1, 6):
        cid = repo.create_chapter(conn, bid, v1 if i <= 2 else v2, i, title=f"T{i}")
        repo.update_chapter(conn, cid, body=f"原文{i}", summary=f"摘要{i}", status="accepted")
    repo.upsert_character(conn, bid, "沈照", core=True, location="山门")
    repo.upsert_character(conn, bid, "阿蘅", location="药庐")
    repo.upsert_character(conn, bid, "老道", alive=False)
    repo.add_foreshadow(conn, bid, 2, "玉佩发烫", "卷末揭示")
    repo.add_fact(conn, bid, "太玄宗禁夜行", 1)
    return bid


def test_load_context_layers(conn, book):
    ctx = load_context(conn, book, recent_n=2)
    assert [c["idx"] for c in ctx.recent] == [4, 5]
    # 本卷(卷 2)章摘要不含最近原文已带的 4、5;封卷的卷 1 章摘要不出现
    assert [i for i, _, _ in ctx.volume_chapter_summaries] == [3]
    assert ctx.past_volume_summaries == [(1, "主角入了太玄宗。")]
    assert ctx.next_idx == 6


def test_load_context_unknown_book(conn):
    with pytest.raises(KeyError):
        load_context(conn, 999)


def test_select_ledger_core_always_noncore_by_outline(conn, book):
    chars = repo.list_characters(conn, book)
    names = lambda sel: {c["name"] for c in sel[0]}  # noqa: E731
    assert names(select_ledger(chars, [], "")) == {"沈照"}
    assert names(select_ledger(chars, [], "阿蘅出场")) == {"沈照", "阿蘅"}


def test_facts_are_not_truncated_and_sealed_ones_come_via_canon(conn, book):
    """不再按条数截断(会先丢最早、最根本的事实):往卷事实走定本,本卷事实逐条全带。"""
    for i in range(3, 6):
        for k in range(30):
            repo.add_fact(conn, book, f"第{i}章事实{k}", i)
    repo.save_bible(conn, book, canon="太玄宗禁夜行(定本)")
    ctx = load_context(conn, book)
    assert len(ctx.facts) == 90 and all(f["established_ch"] >= 3 for f in ctx.facts)  # 卷 1(第1~2章)的不在
    out = render_memory(ctx)
    assert "太玄宗禁夜行(定本)" in out and "第3章事实0" in out and "第5章事实29" in out


def test_duplicate_fact_recorded_once(conn, book):
    assert repo.add_fact(conn, book, "后山有井", 3) is not None
    assert repo.add_fact(conn, book, "后山有井", 4) is None
    assert [f["fact"] for f in repo.list_facts(conn, book)].count("后山有井") == 1


def test_render_memory_contains_all_layers(conn, book):
    out = render_memory(load_context(conn, book, recent_n=2), scope="阿蘅出场")
    for needle in ["少年入宗门", "第1卷:主角入了太玄宗", "下山", "离宗→遇险", "第3章《T3》:摘要3",
                   "沈照(存活)", "阿蘅(存活)", "玉佩发烫"]:
        assert needle in out, needle
    assert "摘要1" not in out  # 封卷后旧卷章摘要不再进 prompt
    assert "太玄宗禁夜行" not in out  # 第 1 章(已封卷)的事实不逐条带;它应已并入定本


def test_dead_character_stays_visible_when_in_outline(conn, book):
    out = render_memory(load_context(conn, book), scope="老道的遗物")
    assert "老道(已死亡)" in out  # 否则模型会让死人复活


def test_render_memory_empty_book(conn):
    bid = repo.create_book(conn, "空书")
    out = render_memory(load_context(conn, bid))
    assert "(尚无)" in out and "(无)" in out


def test_recent_text(conn, book):
    assert "〔第5章《T5》〕\n原文5" in recent_text(load_context(conn, book))
    empty = repo.create_book(conn, "空书")
    assert "开篇" in recent_text(load_context(conn, empty))


def test_render_bible_and_samples():
    bible = {"world": "灵气枯竭", "characters": [{"name": "沈照", "role": "主角", "traits": "腹黑"}],
             "style_fingerprint": "短句,冷幽默", "taboos": ["现代梗"], "style_samples": ["夜很长。"]}
    out = render_bible(bible)
    assert "沈照:主角 腹黑" in out and "短句,冷幽默" in out and "- 现代梗" in out
    assert "〔样章片段1〕\n夜很长。" in render_style_samples(bible)
    assert render_style_samples({"style_samples": []}) == ""
