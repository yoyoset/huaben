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
    assert [o["key"] for o in options_view()] == ["narrative", "prose", "foreshadow", "pacing"]


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
    assert len(c.get("/api/craft/options").json()) == 4
    assert c.get("/api/books/999/craft").status_code == 404
