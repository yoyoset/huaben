"""节奏检查(T012):章纲四标记的硬检查与节奏提醒,以及导入/命令行的接线。"""
import json

from huaben import repo
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.rhythm import main, rhythm_problems, rhythm_warnings
from huaben.script_import import import_book, import_volume, review_volume_script
from test_script_import import BOOK

S = Settings(openrouter_api_key="x", chapter_words=1, _env_file=None)
MODES = ["战", "笑", "情", "谜", "修"]


def ch(i=1, mode="战", tension=3, result="无", gain=""):
    return {"title": f"第{i}章标题", "outline": "事", "when": "第二天", "characters": [],
            "foreshadows": [], "planned_reversals": [], "payoff": "p", "novelty": "", "hook": "h",
            "mode": mode, "tension": tension, "result": result, "gain": gain}


def _n(n, mode="战", tension=3, result="无", gain=""):
    return [ch(i + 1, mode=MODES[i % 5] if mode is None else mode, tension=tension, result=result, gain=gain)
            for i in range(n)]


def test_rhythm_problems_reports_bad_markers():
    assert rhythm_problems([ch(1)]) == []
    bad = [ch(1, mode="打"), ch(2, tension=6), ch(3, tension=True), ch(4, result="赢"), {"mode": "战", "tension": 3}]
    ps = rhythm_problems(bad)
    assert sum("mode" in p for p in ps) == 1 and sum("tension" in p for p in ps) == 2 and sum("result" in p for p in ps) == 2


def test_mode_runs():
    assert any("都是「笑」" in w for w in rhythm_warnings(_n(4, mode="笑", gain="g")))
    assert not any("笑" in w for w in rhythm_warnings(_n(3, mode="笑", gain="g")))
    assert any("都是「战」" in w for w in rhythm_warnings(_n(6, mode="战", gain="g")))
    assert not any("战" in w for w in rhythm_warnings(_n(5, mode="战", gain="g")))


def test_tension_runs():
    assert any("张力都在 4 以上" in w for w in rhythm_warnings(_n(5, mode=None, tension=4, gain="g")))
    assert not any("4 以上" in w for w in rhythm_warnings(_n(4, mode=None, tension=4, gain="g")))
    assert any("张力都在 2 以下" in w for w in rhythm_warnings(_n(4, mode=None, tension=2, gain="g")))
    assert not any("2 以下" in w for w in rhythm_warnings(_n(3, mode=None, tension=2, gain="g")))


def test_no_win_and_no_gain_runs():
    assert any("没有一次胜" in w for w in rhythm_warnings(_n(6, mode=None, gain="g")))
    assert not any("没有一次胜" in w for w in rhythm_warnings(_n(5, mode=None, gain="g")))
    assert any("没有力量上的所得" in w for w in rhythm_warnings(_n(11, mode=None, result="胜")))
    assert not any("没有力量上的所得" in w for w in rhythm_warnings(_n(10, mode=None, result="胜")))


def test_whole_batch_only_after_20():
    assert any("没有一次像样的失败" in w for w in rhythm_warnings(_n(20, mode=None, result="胜", gain="g")))
    assert not any("没有一次像样的失败" in w for w in rhythm_warnings(_n(19, mode=None, result="胜", gain="g")))


def test_a_well_arranged_batch_has_no_warnings():
    chs = []
    for i in range(30):
        chs.append(ch(i + 1, mode=MODES[i % 5], tension=3, result="胜" if i % 3 == 2 else "无",
                      gain="学了一招" if i % 8 == 0 else ""))
    chs[19] = ch(20, mode=MODES[19 % 5], tension=5, result="负")   # 一次像样的失败
    chs[20] = ch(21, mode="情", tension=4, result="胜")            # 一章到位的情感戏 + 最高点
    assert rhythm_warnings(chs) == []


def test_import_volume_returns_warnings_and_review_writes_nothing(conn):
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    data = {"volume": {"goal": "g", "beats": ["a"], "beat_chapters": [4]},
            "chapters": [ch(i + 1, mode="笑", gain="g") for i in range(4)]}
    r = import_volume(conn, FakeLLM([]), S, bid, data)
    assert any("都是「笑」" in w for w in r["rhythm_warnings"])
    # dry_run:只检查、不写库
    bid2 = import_book(conn, {**BOOK, "bible": {**BOOK["bible"], "title": "夜行录二"}})
    assert review_volume_script(conn, bid2, data) == {"problems": [], "rhythm_warnings": ["第 1~4 章连续 4 章都是「笑」"]}
    bad = {"volume": {"goal": "g", "beats": ["a"], "beat_chapters": [1]},
           "chapters": [ch(1), ch(2)]}
    assert review_volume_script(conn, bid2, bad)["problems"]  # 有问题仍返回
    assert repo.list_volumes(conn, bid2) == [] and repo.max_scripted_idx(conn, bid2) == 0


def test_dry_run_endpoint_does_not_write(tmp_path):
    from fastapi.testclient import TestClient

    from huaben.api.app import create_app
    from huaben.db import connect
    s = Settings(openrouter_api_key="x", data_dir=tmp_path, worker_enabled=False, _env_file=None)
    conn = connect(s.db_path)
    repo.create_profile(conn, "我")
    bid = import_book(conn, BOOK)
    c = TestClient(create_app(s))
    data = {"volume": {"goal": "g", "beats": ["a"], "beat_chapters": [4]},
            "chapters": [ch(i + 1, mode="笑", gain="g") for i in range(4)]}
    r = c.post(f"/api/books/{bid}/import/volume?dry_run=1", json=data)
    assert r.status_code == 200 and r.json()["problems"] == [] and r.json()["rhythm_warnings"]
    assert repo.max_scripted_idx(conn, bid) == 0  # 什么都不写库


def test_big_turns_too_close_warn():
    chs = [ch(i + 1) for i in range(9)]
    chs[2]["turn"] = "大"
    chs[8]["turn"] = "大"  # 第 3 和第 9 章,相隔 6 < 8
    assert any("太密" in w for w in rhythm_warnings(chs))
    far = [ch(i + 1) for i in range(12)]
    far[2]["turn"] = "大"
    far[11]["turn"] = "大"  # 相隔 9,不提醒
    assert not any("太密" in w for w in rhythm_warnings(far))


def test_medium_turn_runs_warn():
    chs = [ch(1), ch(2), ch(3)]
    chs[0]["turn"] = "中"
    chs[1]["turn"] = "大"
    chs[2]["turn"] = "中"
    assert any("来不及信" in w for w in rhythm_warnings(chs))
    short = [ch(1), ch(2)]
    short[0]["turn"] = "中"
    short[1]["turn"] = "大"
    assert not any("来不及信" in w for w in rhythm_warnings(short))


def test_turn_marker_validation():
    bad = ch(1)
    bad["turn"] = "巨"
    assert any("turn" in p for p in rhythm_problems([bad]))
    assert rhythm_problems([ch(1)]) == []  # 不填 turn 不报


def test_grip_marker_validation():
    bad = ch(1)
    bad["grip"] = "硬"
    assert any("grip" in p for p in rhythm_problems([bad]))
    assert rhythm_problems([ch(1)]) == []  # 不填 grip 不报


def test_grip_warnings_only_when_marked():
    tight = [ch(i + 1, mode=MODES[i % 5]) for i in range(5)]
    for c in tight:
        c["grip"] = "紧"
    assert any("连续 5 章都是「紧」" in w for w in rhythm_warnings(tight))

    loose = [ch(i + 1, mode=MODES[i % 5]) for i in range(10)]
    for i, c in enumerate(loose):
        c["grip"] = "松" if i == 0 else "中"
    assert any("不到五分之一" in w for w in rhythm_warnings(loose))

    plain = [ch(i + 1, mode=MODES[i % 5]) for i in range(10)]  # 一个都没填:两条都不查
    ws = rhythm_warnings(plain)
    assert not any("都是「紧」" in w for w in ws) and not any("不到五分之一" in w for w in ws)


def test_cli_prints_warnings_or_pass(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"chapters": [ch(i + 1, mode="笑", gain="g") for i in range(4)]}, ensure_ascii=False),
                   encoding="utf-8")
    assert main([str(bad)]) == 0 and "提醒:" in capsys.readouterr().out
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"chapters": [ch(1, mode="笑"), ch(2, mode="战"), ch(3, mode="情")]},
                               ensure_ascii=False), encoding="utf-8")
    assert main([str(good)]) == 0 and "节奏检查通过" in capsys.readouterr().out
