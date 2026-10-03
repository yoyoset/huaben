"""每本书的写法设定(2026-10-03 用户:叙事要大师级、诺兰式结构可选;开书时给模板选,开书后也能改)。"""
import json

from huaben import repo
from huaben.context import load_context
from huaben.craft import DEFAULT, from_book, normalize_craft, options_view, render_craft
from huaben.pipeline.prompts import outline_messages, write_messages

OUTLINE = {"title": "T", "outline": "事", "characters": [], "foreshadows": [], "planned_reversals": [], "hook": "钩"}


def test_unknown_values_fall_back_to_defaults_and_notes_are_capped():
    c = normalize_craft({"narrative": "nonlinear", "prose": "奇怪", "notes": "多写笑点" + "啊" * 2000})
    assert c["narrative"] == "nonlinear" and c["prose"] == DEFAULT["prose"] and len(c["notes"]) == 1000
    assert normalize_craft(None) == {**DEFAULT, "notes": ""}
    assert from_book({"craft": "不是 JSON"}) == {**DEFAULT, "notes": ""}  # 坏数据不让书写不下去


def test_render_turns_choices_into_concrete_instructions():
    text = render_craft({"narrative": "nonlinear", "foreshadow": "deep", "notes": "主角腹黑"})
    assert "非线性·诺兰式" in text and "信息差" in text and "尾田式" in text and "读者的补充要求:主角腹黑" in text
    assert [o["key"] for o in options_view()] == ["narrative", "prose", "imagination", "foreshadow", "pacing"]
    assert "不照搬类型默认模板" in render_craft({"imagination": "wild"})


def test_book_craft_reaches_outline_and_writer(conn):
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, status="active")
    repo.update_book(conn, bid, craft=json.dumps({"narrative": "braided", "notes": "每章至少四个笑点"}, ensure_ascii=False))
    ctx = load_context(conn, bid)
    outline_user = outline_messages(ctx)[1]["content"]
    write_user = write_messages(ctx, OUTLINE, 1000)[1]["content"]
    for text in (outline_user, write_user):
        assert "多线交织" in text and "每章至少四个笑点" in text
    assert write_user.index("【写法设定") > write_user.index("【本章工单】")  # 写法紧贴硬性要求,不被前文淹没


def test_craft_api_round_trip(tmp_path):
    from test_voice_api import setup
    s, conn, (a, b), c = setup(tmp_path)
    assert c.get(f"/api/books/{a}/craft").json() == {**DEFAULT, "notes": ""}  # 旧书:默认
    saved = c.put(f"/api/books/{a}/craft", json={"narrative": "nonlinear", "pacing": "瞎写", "notes": "要好笑"}).json()
    assert saved["narrative"] == "nonlinear" and saved["pacing"] == DEFAULT["pacing"]
    assert c.get(f"/api/books/{a}/craft").json() == saved
    assert len(c.get("/api/craft/options").json()) == 5
    assert c.get("/api/books/999/craft").status_code == 404


def test_world_expansion_appends_and_keeps_original(tmp_path):
    """补充原创设定:原世界观一字不动,补充带日期小标题追加在后面;已写章节摘要交给模型,防止新设定和已读内容打架。"""
    from huaben.llm_fake import FakeLLM
    from huaben.pipeline.world_expand import append_section, expand_messages
    assert append_section("旧设定。\n", "新机制", "2026-10-03") == "旧设定。\n\n【原创设定补充 2026-10-03】\n新机制"
    msgs = expand_messages({"world": "五境修炼"}, "梗概", ["第1章《夜账》:算账"], {"imagination": "wild"})
    assert "第1章《夜账》:算账" in msgs[1]["content"] and "核心力量机制" in msgs[1]["content"]

    from test_voice_api import setup
    s, conn, (a, b), c = setup(tmp_path)
    repo.save_bible(conn, a, world="五境修炼。")
    c.app.state.llm = FakeLLM([json.dumps({"additions": "算筹为刃", "why": "更新"}, ensure_ascii=False)])
    c.app.state.llm_injected = True
    r = c.post(f"/api/books/{a}/world/expand").json()
    assert r == {"additions": "算筹为刃", "why": "更新"}
    world = repo.get_bible(conn, a)["world"]
    assert world.startswith("五境修炼。") and world.endswith("算筹为刃")


def test_editor_sees_recent_hooks_and_is_told_to_vary(conn):
    """《算尽仙朝》实测:第 1、3、5 章都以"算盘残片发烫浮现一行字"收尾。编辑要看到最近用过的钩子并换一种。"""
    bid = repo.create_book(conn, "x")
    vid = repo.create_volume(conn, bid, 1, status="active")
    for i, hook in enumerate(["残片发烫,浮现一行字", "残片又发烫了"], 1):
        cid = repo.create_chapter(conn, bid, vid, i, title=f"T{i}", outline=json.dumps({"hook": hook}, ensure_ascii=False))
        repo.update_chapter(conn, cid, body="b", summary="s", status="accepted")
    user = outline_messages(load_context(conn, bid))[1]["content"]
    assert "- 第1章:残片发烫,浮现一行字" in user and "不要再靠同一个道具或同一种异象收尾" in user
