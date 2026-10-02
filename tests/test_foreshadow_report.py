"""伏笔回收报告:按卷的计划/实收/未收与全书汇总。"""
from huaben.foreshadow_report import build_report


def fs(i, planted, resolved=None):
    return {"id": i, "content": f"伏笔{i}", "planted_ch": planted,
            "status": "resolved" if resolved else "planted", "resolved_ch": resolved}


VOLS = [{"id": 10, "idx": 1, "status": "sealed", "resolve": [1, 2]},
        {"id": 11, "idx": 2, "status": "active", "resolve": [3]}]
RANGES = {10: (1, 10), 11: (11, 15)}


def test_per_volume_plan_vs_actual():
    rep = build_report(VOLS, RANGES, [fs(1, 2, 8), fs(2, 3), fs(3, 9, 12), fs(4, 13)], now_idx=15)
    v1, v2 = rep["volumes"]
    assert v1 == {"idx": 1, "status": "sealed", "chapters": (1, 10), "planted": 3, "planned_resolve": [1, 2],
                  "resolved": [1], "missed": [2]}
    assert v2["planted"] == 1 and v2["resolved"] == [3] and v2["missed"] == []


def test_totals_and_oldest_open():
    rep = build_report(VOLS, RANGES, [fs(1, 2, 8), fs(2, 3), fs(3, 9, 12), fs(4, 13)], now_idx=15)
    t = rep["total"]
    assert (t["planted"], t["resolved"], t["open"]) == (4, 2, 2)
    assert t["open_by_scale"] == {"short": 0, "medium": 2, "long": 0}  # 没标大小的旧伏笔按中线算
    assert t["avg_chapters_to_resolve"] == 4.5  # (8-2 + 12-9) / 2
    assert [(o["id"], o["age"]) for o in t["oldest_open"]] == [(2, 12), (4, 2)]


def test_volume_without_chapters_and_empty_book():
    rep = build_report([{"id": 1, "idx": 1, "status": "active", "resolve": []}], {}, [], now_idx=0)
    assert rep["volumes"][0]["chapters"] is None and rep["total"]["avg_chapters_to_resolve"] is None
