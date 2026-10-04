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
    assert [o["key"] for o in options_view()] == ["narrative", "prose", "imagination", "foreshadow", "pacing", "power"]
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
    assert len(c.get("/api/craft/options").json()) == 6
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


def test_original_settings_must_show_up_in_chapters(conn):
    """2026-10-03 实测:补充了原创设定后,第 11 章两个模型都没用上——章纲从没被要求"本章用哪一样"。"""
    from huaben.pipeline.normalize import normalize_outline
    from huaben.pipeline.prompts import work_order
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, status="active")
    repo.update_book(conn, bid, craft=json.dumps({"imagination": "wild"}))
    assert "novelty 多数章要填" in outline_messages(load_context(conn, bid))[1]["content"]
    repo.update_book(conn, bid, craft=json.dumps({"imagination": "conventional"}))
    assert "novelty 可以留空" in outline_messages(load_context(conn, bid))[1]["content"]
    o = normalize_outline({**OUTLINE, "novelty": "借据到期,天地来平账"})
    assert "本章的新奇之处" in work_order(5, o) and "借据到期" in work_order(5, o)
    assert normalize_outline(OUTLINE)["novelty"] == "" and "新奇之处" not in work_order(5, normalize_outline(OUTLINE))


def test_every_chapter_must_pay_something_off(conn):
    """2026-10-03 读生产书:相邻几章只有新谜题、没有兑现,主角被动收纸条。章纲要写本章兑现,作者要写足。"""
    from huaben.pipeline.normalize import normalize_outline
    from huaben.pipeline.prompts import work_order
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, status="active")
    user = outline_messages(load_context(conn, bid))[1]["content"]
    assert "payoff 必填" in user and "不要让他只是被动地收到信息" in user
    o = normalize_outline({**OUTLINE, "payoff": "王师兄当众出丑,周小满白赚两瓶丹"})
    assert "本章兑现(要写足" in work_order(5, o) and "白赚两瓶丹" in work_order(5, o)


def test_numbers_must_be_readable_logged_and_checked(conn):
    """《算尽仙朝》整屏数字、两章说法打架;MiMo Pro 稿里"一瓶十粒,三瓶九十粒"。写的时候要读得懂,入账要登记数字、核对算术。"""
    from huaben.pipeline.prompts import ledger_messages
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, status="active")
    ctx = load_context(conn, bid)
    assert "一处推理只亮一两个关键数字" in write_messages(ctx, OUTLINE, 1000)[1]["content"]
    ledger = ledger_messages(ctx, OUTLINE, "正文")[1]["content"]
    assert "具体数字(数量、价格、比例、日期)也作为事实登记" in ledger and "算术是否算对" in ledger
    # 2026-10-03:软观察(拿不准/建议/读感)走 editor_notes,不打回;只有"读者当场能指出"的硬伤进 contradictions
    assert "editor_notes" in ledger and "拿不准的" in ledger and "不要写进 contradictions" in ledger


def test_power_category_and_tone_title():
    """T031:能力与战斗可三档;写法设定是基调,不是全书遵守的定额。"""
    assert normalize_craft({})["power"] == "core"          # 不填 = 现在的行为
    assert normalize_craft({"power": "light"})["power"] == "light"
    assert normalize_craft({"power": "乱填"})["power"] == "core"
    text = render_craft({"power": "light"})
    assert "能力与战斗" in text and "点到为止" in text
    assert "全书的基调" in text and "全书遵守" not in text


def test_signature_rule_by_power():
    from huaben.pipeline.rules import SIGNATURE_LIGHT, SIGNATURE_RULE, signature_rule
    assert signature_rule({"power": "core"}) == SIGNATURE_RULE
    assert signature_rule({"power": "light"}) == SIGNATURE_LIGHT
    assert signature_rule({"power": "none"}) == ""


def test_signature_requirement_follows_power_category(conn):
    """招牌能力按书的档位发:不写的书整条去掉、不留空行;点到为止的只要求前后一致。"""
    from huaben.pipeline.rules import BOND_RULE, SIGNATURE_LIGHT, SIGNATURE_RULE, SPEECH_RULE
    bid = repo.create_book(conn, "x")
    repo.create_volume(conn, bid, 1, status="active")
    repo.update_book(conn, bid, craft=json.dumps({"power": "none"}))
    ctx = load_context(conn, bid)
    outline_none = outline_messages(ctx)[1]["content"]
    assert SIGNATURE_RULE not in outline_none and "招牌能力" not in outline_none
    assert f"{BOND_RULE}\n{SPEECH_RULE}" in outline_none  # 空能力档:整行去掉,不留空行
    assert "招牌能力" not in write_messages(ctx, OUTLINE, 1000)[1]["content"]

    repo.update_book(conn, bid, craft=json.dumps({"power": "light"}))
    light = write_messages(load_context(conn, bid), OUTLINE, 1000)[1]["content"]
    assert SIGNATURE_LIGHT in light and "工具人" not in light

    repo.update_book(conn, bid, craft=json.dumps({"power": "core"}))
    default = write_messages(load_context(conn, bid), OUTLINE, 1000)[1]["content"]
    assert "工具人" in default  # 默认仍是现状


def test_wild_imagination_is_a_tone_not_every_chapter():
    from huaben.craft import CATEGORIES, novelty_rule
    assert "日常和过渡的章不必硬塞" in CATEGORIES["imagination"][1]["wild"][1]
    assert "可以空" in novelty_rule({"imagination": "wild"})
