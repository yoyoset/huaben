"""碎句检查(T017):逗号密度超标的稿子打回,导入稿只留痕。"""
from huaben import repo
from huaben.config import Settings
from huaben.pipeline.chapter import generate_chapter
from huaben.pipeline.chop import chop_problems, comma_density
from scripted_llm import ScriptedLLM

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)


def test_comma_density_counts_only_fullwidth_commas():
    assert comma_density("他的手，停了。") == 1 / 7 * 100  # 7 个非空白字符、1 个逗号
    assert comma_density("") == 0.0
    assert comma_density("a,b,c") == 0.0  # 半角逗号不计
    assert comma_density("他，\n 停。") == comma_density("他，停。")  # 换行与空格不计入字数


def test_chop_problems_respects_limit_and_min_length():
    assert chop_problems("好字。" * 200) == []  # 600 字、密度 0
    dense = "ab，cdef。" * 75  # 600 字、每 8 字一个逗号,密度 12.5
    got = chop_problems(dense)
    assert len(got) == 1 and got[0].startswith("句子被逗号切得太碎") and "12.5" in got[0]
    assert chop_problems("ab，cdef。" * 25) == []  # 同样密度但只有 200 字,不量


def test_chopped_first_draft_is_rejected_then_rewritten(conn):
    bid = repo.create_book(conn, "诡仙")
    repo.create_volume(conn, bid, 1, goal="入门", status="active")
    llm = ScriptedLLM(choppy={1})
    ch = generate_chapter(conn, llm, S, bid)
    assert ch["status"] == "accepted" and ch["attempts"] == 2
    notes = [r[0] for r in conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE 'draft: 句子被逗号切得太碎%'")]
    assert len(notes) == 1


def test_imported_chopped_text_only_warns(conn):
    from huaben.llm_fake import FakeLLM
    from huaben.script_import import import_book, import_volume
    from huaben.script_text import import_chapter_texts
    from test_script_import import BOOK
    from test_script_volume import ch
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    import_volume(conn, FakeLLM([]), S, bid, {"volume": {"goal": "入门", "beats": ["起"], "beat_chapters": [1]},
                                              "chapters": [ch(1)]})
    import_chapter_texts(conn, bid, [{"idx": 1, "body": "（第1章）" + "他的手，停了。" * 100}])
    assert generate_chapter(conn, ScriptedLLM(), S, bid)["status"] == "accepted"
    notes = [r[0] for r in conn.execute("SELECT note FROM pipeline_runs WHERE note LIKE '%导入正文的提醒(未打回)%'")]
    assert any("句子被逗号切得太碎" in n for n in notes)
