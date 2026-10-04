"""章纲里的"原话"必须一字不改地进正文(T014)。"""
import json

from huaben import repo
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.pipeline.chapter import generate_chapter
from huaben.pipeline.normalize import normalize_outline
from huaben.pipeline.prompts import work_order
from huaben.verbatim import ending_problem, lines_feedback, missing_lines


def test_halfwidth_and_fullwidth_punct_are_the_same():
    assert missing_lines("他说:戏不错，跟我走一趟？", ['"戏不错,跟我走一趟?"']) == []
    assert missing_lines('他说:"戏不错,跟我走一趟?"', ["戏不错，跟我走一趟？"]) == []
    assert missing_lines("他说:戏不赖，跟我走一趟？", ['"戏不错,跟我走一趟?"']) == ['"戏不错,跟我走一趟?"']
    assert ending_problem("前面。" * 50 + "跟我走一趟？", "跟我走一趟?") == []

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)


def test_missing_lines_ignores_quotes_and_whitespace():
    assert missing_lines("沈照说:我不跑了。从此不逃。", ["我不跑了。"]) == []
    assert missing_lines("沈照说:“我不跑了。”", ['"我不跑了。"']) == []  # 直引号换弯引号不算
    assert missing_lines("沈照说:我不\n跑了。", ["我不跑了。"]) == []      # 句中换行不算
    assert missing_lines("沈照说:我不走了。", ["我不跑了。"]) == ["我不跑了。"]  # 改一个字就算缺
    assert missing_lines("正文", []) == []
    assert missing_lines("正文", ["", "   "]) == []  # 空句子被忽略
    assert lines_feedback(["我不跑了。"])[0].endswith("我不跑了。")


def test_normalize_outline_keeps_lines():
    base = {"title": "T", "outline": "事"}
    assert normalize_outline({**base, "lines": ["我不跑了。", "开灯!"]})["lines"] == ["我不跑了。", "开灯!"]
    assert normalize_outline(base)["lines"] == []


def test_work_order_shows_verbatim_lines_only_if_present():
    o = {"title": "T", "outline": "事", "characters": [], "foreshadows": [], "planned_reversals": [],
         "hook": "钩", "lines": ["我不跑了。", "开灯!"]}
    w = work_order(3, o)
    assert "必须一字不改" in w and "- 我不跑了。" in w and "- 开灯!" in w
    assert "必须一字不改" not in work_order(3, {**o, "lines": []})


def test_missing_line_rejects_first_draft_then_accepts(conn):
    bid = repo.create_book(conn, "诡仙")
    repo.create_volume(conn, bid, 1, goal="入门", status="active")
    repo.upsert_character(conn, bid, "沈照", core=True)
    outline = json.dumps({"title": "立誓", "outline": "沈照立誓。", "characters": ["沈照"], "foreshadows": [],
                          "planned_reversals": [], "hook": "灯灭了", "lines": ["我不跑了。"]}, ensure_ascii=False)
    led = json.dumps({"summary": "沈照立誓。", "characters": [], "foreshadows_new": [], "foreshadows_update": [],
                      "facts": [], "contradictions": []}, ensure_ascii=False)
    llm = FakeLLM([outline, "沈照站在井边,天很黑。", "沈照站在井边说:我不跑了。天很黑。", led])
    ch = generate_chapter(conn, llm, S, bid)
    assert ch["status"] == "accepted" and ch["attempts"] == 2  # 第一稿被打回,第二稿定稿
    notes = [r[0] for r in conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE 'draft:%'")]
    assert len(notes) == 1 and "我不跑了" in notes[0]  # 第一稿被打回,留痕
    assert "没有出现在正文里" in llm.calls[2][-1]["content"]  # 第二次写作者时带上了打回理由


def test_ending_problem_checks_presence_and_position():
    assert ending_problem("前面。" * 50 + "跟我走一趟。", "跟我走一趟。") == []
    assert "没有写到" in ending_problem("前面很长。" * 50, "跟我走一趟。")[0]
    assert "写过头了" in ending_problem("跟我走一趟。" + "后面很长。" * 100, "跟我走一趟。")[0]
    assert ending_problem("正文", "") == []
    assert ending_problem("前面。“跟我走一趟。”", '"跟我走一趟。"') == []  # 引号差异不算


def test_work_order_shows_ending_stop_line_only_if_present():
    o = {"title": "T", "outline": "事", "characters": [], "foreshadows": [], "planned_reversals": [],
         "hook": "钩", "ending": "跟我走一趟。"}
    assert "写到这句就停" in work_order(3, o) and "跟我走一趟。" in work_order(3, o)
    assert "写到这句就停" not in work_order(3, {**o, "ending": ""})


def test_overshoot_rejects_first_draft_then_accepts(conn):
    bid = repo.create_book(conn, "诡仙")
    repo.create_volume(conn, bid, 1, goal="入门", status="active")
    repo.upsert_character(conn, bid, "沈照", core=True)
    outline = json.dumps({"title": "出门", "outline": "沈照出门。", "characters": ["沈照"], "foreshadows": [],
                          "planned_reversals": [], "hook": "灯灭了", "ending": "跟我走一趟。"}, ensure_ascii=False)
    led = json.dumps({"summary": "沈照出门。", "characters": [], "foreshadows_new": [], "foreshadows_update": [],
                      "facts": [], "contradictions": []}, ensure_ascii=False)
    first = "沈照出门。跟我走一趟。" + "天很黑,风很冷,路很长。" * 40  # 写过头:后面还有 400 字
    second = "沈照出门。天很黑。" + "风很冷。" * 20 + "跟我走一趟。"  # 停在这句
    llm = FakeLLM([outline, first, second, led])
    ch = generate_chapter(conn, llm, S, bid)
    assert ch["status"] == "accepted" and ch["attempts"] == 2
    notes = [r[0] for r in conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE 'draft:%'")]
    assert len(notes) == 1 and "写过头了" in notes[0]


def _grip_book(conn):
    bid = repo.create_book(conn, "诡仙")
    repo.create_volume(conn, bid, 1, goal="入门", status="active")
    repo.upsert_character(conn, bid, "沈照", core=True)
    return bid


def _grip_outline(**kw):
    d = {"title": "出井", "outline": "沈照出井。", "characters": ["沈照"], "foreshadows": [],
         "planned_reversals": [], "hook": "钩"}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


def _plain_ledger(contradictions=None):
    return json.dumps({"summary": "沈照出井。", "characters": [], "foreshadows_new": [], "foreshadows_update": [],
                       "facts": [], "contradictions": contradictions or []}, ensure_ascii=False)


def test_medium_grip_skips_ending_check(conn):
    """中档结尾只要"意思到了",正文没写那句原话也不打回。"""
    bid = _grip_book(conn)
    outline = _grip_outline(grip="中", ending="跟我走一趟。")
    ch = generate_chapter(conn, FakeLLM([outline, "沈照出井了。", _plain_ledger()]), S, bid)
    assert ch["status"] == "accepted" and ch["attempts"] == 1


def test_no_grip_still_enforces_ending(conn):
    """不填档位 = 老行为:结尾原话没写到就重写一稿。"""
    bid = _grip_book(conn)
    outline = _grip_outline(ending="跟我走一趟。")
    llm = FakeLLM([outline, "沈照出井了。", "沈照出井了。跟我走一趟。", _plain_ledger()])
    ch = generate_chapter(conn, llm, S, bid)
    assert ch["attempts"] == 2


def test_loose_grip_logs_plain_contradiction(conn):
    """松档:编辑挑出的普通读感疑点不打回,只留一条"矛盾(未打回)"记录。"""
    bid = _grip_book(conn)
    outline = _grip_outline(grip="松")
    led = _plain_ledger([{"what": "音量没交代", "planned": False}])
    ch = generate_chapter(conn, FakeLLM([outline, "沈照出井了。", led]), S, bid)
    assert ch["status"] == "accepted" and ch["attempts"] == 1
    note = conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE '矛盾(未打回)%'").fetchone()
    assert note is not None and "音量没交代" in note["note"]


def test_loose_grip_rejects_must_contradiction(conn):
    """松档也拦"不能错:"开头的原则性矛盾。"""
    bid = _grip_book(conn)
    outline = _grip_outline(grip="松", must=["厉九不出手"])
    bad = _plain_ledger([{"what": "不能错:厉九出手了", "planned": False}])
    llm = FakeLLM([outline, "沈照出井了。", bad, "沈照出井,厉九没出手。", _plain_ledger()])
    ch = generate_chapter(conn, llm, S, bid)
    assert ch["attempts"] == 2
    assert any("不能错:厉九出手了" in r[0] for r in
               conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE 'contradiction:%'"))
