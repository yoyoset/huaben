"""章纲里的"原话"必须一字不改地进正文(T014)。"""
import json

from huaben import repo
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.pipeline.chapter import generate_chapter
from huaben.pipeline.normalize import normalize_outline
from huaben.pipeline.prompts import work_order
from huaben.verbatim import lines_feedback, missing_lines

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
