"""口头禅统计(T025):纯函数计数与只读命令行的接线。"""
from huaben.tics import main, tic_counts, tic_report


def test_tic_counts_basic():
    r = tic_counts("他一级一级往上走。血一滴，一滴，落下来。他一动不动。")
    assert r["redup"] == 2
    assert r["fixed"] == {"一动不动": 1}
    assert ("一级一级", 1) in r["top_redup"] and ("一滴一滴", 1) in r["top_redup"]


def test_tic_counts_empty():
    r = tic_counts("")
    assert r["chars"] == 0 and r["redup_per_k"] == 0.0


def test_report_dense_mark():
    assert "【密】" in tic_report({1: "一滴一滴" * 3 + "字" * 994})[0]
    assert "【密】" not in tic_report({1: "一滴一滴" + "字" * 998})[0]


def test_report_sorts_and_totals():
    lines = tic_report({2: "一动不动。", 1: "他一动不动。"})
    assert lines[0].startswith("第01章") and lines[-1].startswith("合计")


def test_main_reads_directory(tmp_path):
    (tmp_path / "01.txt").write_text("他一动不动。", encoding="utf-8")
    (tmp_path / "02.txt").write_text("血一滴，一滴，落下来。", encoding="utf-8")
    assert main([str(tmp_path)]) == 0
    assert main([str(tmp_path / "nope")]) == 1
