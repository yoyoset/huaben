"""伏笔回收报告:对应 v0 验收项"卷内伏笔有回收记录"。

按卷列出:本卷埋了几条、计划要收哪些、实际在本卷内收了哪些、计划却没收的;再给全书汇总
(已埋/已收/未收、平均几章后回收、拖得最久的未收伏笔)。
build_report 是纯函数,load 只负责取数。
"""
from . import repo


def build_report(volumes: list[dict], ranges: dict[int, tuple[int, int]], foreshadows: list[dict],
                 now_idx: int) -> dict:
    """ranges:卷 id → (该卷第一章, 最后一章);还没写章的卷没有条目。now_idx:最新定稿章序号。"""
    by_id = {f["id"]: f for f in foreshadows}

    def in_range(ch, vid):
        lo_hi = ranges.get(vid)
        return ch is not None and lo_hi is not None and lo_hi[0] <= ch <= lo_hi[1]

    per_volume = []
    for v in volumes:
        planned = [i for i in v["resolve"] if isinstance(i, int)]
        resolved_here = sorted(f["id"] for f in foreshadows
                               if f["status"] == "resolved" and in_range(f["resolved_ch"], v["id"]))
        per_volume.append({
            "idx": v["idx"], "status": v["status"], "chapters": ranges.get(v["id"]),
            "planted": sum(1 for f in foreshadows if in_range(f["planted_ch"], v["id"])),
            "planned_resolve": planned,
            "resolved": resolved_here,
            # 已封卷才谈得上"没收";进行中的卷只列"尚未收"
            "missed": [i for i in planned if by_id.get(i, {}).get("status") != "resolved"],
        })
    resolved = [f for f in foreshadows if f["status"] == "resolved" and f["resolved_ch"] is not None]
    open_fs = sorted((f for f in foreshadows if f["status"] != "resolved"), key=lambda f: f["planted_ch"])
    return {
        "volumes": per_volume,
        "total": {
            "planted": len(foreshadows), "resolved": len(resolved), "open": len(open_fs),
            "avg_chapters_to_resolve": (sum(f["resolved_ch"] - f["planted_ch"] for f in resolved) / len(resolved)
                                        if resolved else None),
            "oldest_open": [{"id": f["id"], "content": f["content"], "age": now_idx - f["planted_ch"]}
                            for f in open_fs[:3]],
        },
    }


def load(conn, book_id: int) -> dict:
    return build_report(repo.list_volumes(conn, book_id), repo.volume_chapter_ranges(conn, book_id),
                        repo.list_foreshadows(conn, book_id),
                        repo.next_chapter_idx(conn, book_id) - 1)
