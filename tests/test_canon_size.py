import json
import logging

from huaben import repo
from huaben.canon_size import CANON_WARN_CHARS, canon_size, seal_note
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.pipeline.volume import plan_volume, seal_volume
from huaben.stats import book_stats

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)
PLAN = json.dumps({"goal": "g", "beats": ["a"], "plant": [], "resolve": [], "target_chapters": 5}, ensure_ascii=False)


def seal_with(canon):
    return json.dumps({"volume_summary": "卷摘要", "synopsis": "梗概", "canon": canon}, ensure_ascii=False)


def sealed_book(conn, canon, old_canon=""):
    bid = repo.create_book(conn, "书")
    repo.save_bible(conn, bid, canon=old_canon)
    v = plan_volume(conn, FakeLLM([PLAN]), S, bid)
    repo.add_fact(conn, bid, "后山有井", 1)
    seal_volume(conn, FakeLLM([seal_with(canon)]), S, bid, v)
    return bid


def test_canon_size_counts_chars_and_nonblank_lines():
    assert canon_size(None) == {"chars": 0, "lines": 0, "warn_chars": CANON_WARN_CHARS, "too_long": False}
    s = canon_size("  后山有井\n\n宗门禁夜行 \n")
    assert s["chars"] == len("后山有井\n\n宗门禁夜行") and s["lines"] == 2 and not s["too_long"]
    assert canon_size("字" * (CANON_WARN_CHARS + 1))["too_long"]
    assert not canon_size("字" * CANON_WARN_CHARS)["too_long"]  # 恰好等于观测线不告警


def test_seal_note_shows_growth_and_flags_too_long():
    assert seal_note("", "后山有井") == "定本 0→4 字"
    assert "建议检查" in seal_note("a", "字" * (CANON_WARN_CHARS + 1))


def test_seal_records_canon_size_in_run_log(conn):
    bid = sealed_book(conn, ["后山有井", "宗门禁夜行"], old_canon="后山有井")
    # 同一步骤先有一条模型调用记录(note 为空),对账留痕是最后一条
    note = conn.execute("SELECT note FROM pipeline_runs WHERE book_id=? AND step='volume_seal' ORDER BY id DESC",
                        (bid,)).fetchone()[0]
    assert "全部回收" in note and "定本 4→10 字" in note  # 对账信息保留,字数变化追加在后面


def test_too_long_canon_logs_warning_but_is_kept_whole(conn, caplog):
    long = ["设定" * 30] * 80  # 4800 字 + 换行
    with caplog.at_level(logging.WARNING, logger="huaben.volume"):
        bid = sealed_book(conn, long)
    assert any("超过观测线" in r.getMessage() for r in caplog.records)
    assert repo.get_bible(conn, bid)["canon"] == "\n".join(long)  # 只告警,不截断


def test_stats_reports_canon_size(conn):
    bid = sealed_book(conn, ["后山有井"])
    assert book_stats(conn, bid)["canon"]["chars"] == 4
    assert book_stats(conn, repo.create_book(conn, "空"))["canon"]["chars"] == 0
