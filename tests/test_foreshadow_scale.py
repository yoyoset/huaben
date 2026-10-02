"""伏笔分大小(短线 / 中线 / 长线)。2026-10-02 用户:伏笔太死,有的该很短、有的该很长。
生产库实测:14 章埋 23 条只收 1 条,"明天赴约"和"女主身世"记得一模一样。"""
from huaben import repo
from huaben.context import load_context
from huaben.foreshadow_scale import OPEN_LIMIT, due_state, normalize_scale, planting_rule
from huaben.pipeline.ledger_apply import apply_ledger
from huaben.pipeline.normalize import normalize_ledger
from huaben.pipeline.prompts import outline_messages
from huaben.render import due_foreshadow_ids, render_memory


def f(ch, scale, i=1):
    return {"id": i, "planted_ch": ch, "scale": scale}


def test_scale_aliases_default_to_medium():
    assert [normalize_scale(x) for x in ("short", "短线", "小", " Long ", "主线", "中", None, "", "奇怪")] == \
        ["short", "short", "short", "long", "long", "medium", "medium", "medium", "medium"]


def test_short_threads_fall_due_quickly_and_long_ones_never_do_mid_volume():
    assert due_state(f(10, "short"), 12, 20, 1) == "early"
    assert due_state(f(10, "short"), 13, 20, 1) == "due"
    assert due_state(f(10, "short"), 16, 20, 1) == "overdue"
    assert due_state(f(10, "medium"), 16, 10, 1) == "early"
    assert due_state(f(10, "medium"), 16, 3, 1) == "due"        # 本卷只剩 3 章
    assert due_state(f(10, "medium"), 32, 25, 31) == "overdue"  # 上一卷埋的中线还没收
    assert due_state(f(1, "long"), 200, 0, 181) == "hold"       # 长线:只推进不揭底


def test_planting_rule_names_due_threads_and_stops_new_ones_when_too_many_open():
    assert "本章至少实打实地回收一条" in planting_rule([], [3, 5]) and "#3、#5" in planting_rule([], [3, 5])
    many = [f(1, "short", i) for i in range(OPEN_LIMIT + 1)]
    assert "不要再埋新的中线或长线伏笔" in planting_rule(many, [])
    longs = [f(1, "long", i) for i in range(OPEN_LIMIT + 1)]
    assert "不要再埋" not in planting_rule(longs, [])  # 长线本来就该慢慢挂着,不算"欠账"


def _book(conn, chapters_done=6):
    bid = repo.create_book(conn, "x")
    vid = repo.create_volume(conn, bid, 1, status="active")
    for i in range(1, chapters_done + 1):
        cid = repo.create_chapter(conn, bid, vid, i, title=f"T{i}")
        repo.update_chapter(conn, cid, body="b", summary="s", status="accepted")
    return bid, vid


def test_ledger_records_scale(conn):
    bid, vid = _book(conn, 1)
    cid = repo.create_chapter(conn, bid, vid, 2, title="T2")
    ledger = normalize_ledger({"summary": "s", "characters": [], "foreshadows_update": [], "facts": [],
                               "contradictions": [], "foreshadows_new": [
                                   {"content": "明天再来", "payoff_plan": "下章", "scale": "短线"},
                                   {"content": "她的身世", "payoff_plan": "全书", "scale": "long"}]})
    apply_ledger(conn, bid, cid, 2, ledger)
    assert [(x["content"], x["scale"]) for x in repo.list_foreshadows(conn, bid)] == [("明天再来", "short"), ("她的身世", "long")]


def test_editor_is_told_which_threads_are_due(conn):
    bid, _ = _book(conn, 6)  # 下一章是第 7 章
    short = repo.add_foreshadow(conn, bid, 2, "明天再来", scale="short")       # 已埋 5 章:该收了
    fresh = repo.add_foreshadow(conn, bid, 6, "刚埋的小谜", scale="short")     # 才 1 章:还早
    repo.add_foreshadow(conn, bid, 1, "她的身世", scale="long")
    ctx = load_context(conn, bid)
    assert due_foreshadow_ids(ctx) == [short]
    memory = render_memory(ctx)
    assert f"#{short} [短线·该收了]" in memory and f"#{fresh} [短线]" in memory and "[长线·只推进不揭底]" in memory
    user = outline_messages(ctx)[1]["content"]
    assert f"本章至少实打实地回收一条(给出答案,不是再加一层谜):#{short}。" in user
