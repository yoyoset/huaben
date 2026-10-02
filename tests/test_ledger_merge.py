"""入账合并人物现状(路线 25)。

实测曾出现:模型照入账格式示例把每个字段都填上(空串/空列表/core=false),一条"只换了地点"的入账
就让主角的能力、关系、已知信息清空,core 变 false(从此不再每章必带)。
"""
from huaben import repo
from huaben.pipeline.ledger_apply import apply_ledger, merge_character
from huaben.pipeline.normalize import normalize_character
from huaben.pipeline.prompts import LEDGER_SCHEMA

HERO = {"name": "沈照", "alive": True, "location": "后山古井", "abilities": "夜视", "relations": "阿蘅的师兄",
        "knows": ["井底有尸"], "core": True, "profile": "主角,腹黑"}
FILLED = {"name": "沈照", "profile": "", "alive": True, "location": "县衙", "abilities": "", "relations": "",
          "knows": [], "core": False}  # 照旧示例填满、只有地点真的变了


def test_schema_shaped_entry_only_changes_what_changed():
    m = merge_character(HERO, normalize_character(FILLED))
    assert m["location"] == "县衙"
    assert (m["abilities"], m["relations"], m["knows"], m["profile"]) == ("夜视", "阿蘅的师兄", ["井底有尸"], "主角,腹黑")


def test_ledger_cannot_change_core_either_way():
    assert merge_character(HERO, {"name": "沈照", "core": False})["core"] is True   # 不能降级主角
    assert merge_character(None, {"name": "路人", "core": True})["core"] is False  # 也不能把路人升为每章必带


def test_real_changes_still_apply():
    m = merge_character(HERO, {"name": "沈照", "alive": False, "knows": ["井底有尸", "师父是凶手"], "abilities": "失明"})
    assert m["alive"] is False and m["knows"] == ["井底有尸", "师父是凶手"] and m["abilities"] == "失明"


def test_revival_is_applied_but_flagged(conn):
    bid = repo.create_book(conn, "书")
    vid = repo.create_volume(conn, bid, 1, status="active")
    cid = repo.create_chapter(conn, bid, vid, 1)
    repo.upsert_character(conn, bid, "老道", alive=False)
    ledger = {"summary": "s", "characters": [{"name": "老道", "alive": True}], "foreshadows_new": [],
              "foreshadows_update": [], "facts": []}
    warnings = apply_ledger(conn, bid, cid, 1, ledger)
    assert any("由已故变为在世" in w for w in warnings)  # 可能是有意反转:不拦,留痕
    assert repo.list_characters(conn, bid)[0]["alive"] is True


def test_schema_no_longer_invites_core_or_empty_values():
    assert '"core"' not in LEDGER_SCHEMA
    assert "只写本章有变化的字段" in LEDGER_SCHEMA and '"location": ""' not in LEDGER_SCHEMA
