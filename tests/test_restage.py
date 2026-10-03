"""打回"重演上一章"(2026-10-03 读生产书:《杂役仙尊》13、14 章开场几乎一样;《算尽仙朝》第 9 章把第 8 章的账又算一遍)。
阈值依据见 huaben/pipeline/restage.py 模块说明(生产两本书 23 对相邻章实测)。"""
import random

from huaben import repo
from huaben.context import load_context
from huaben.pipeline.prompts import outline_messages
from huaben.pipeline.restage import opening_similarity, phrase_overlap, restage_problems

POOL = "山门灯火竹林古井石阶铜钟药炉账册长廊月色旧剑雨声茶棚渡口城楼柳岸雪夜残碑酒肆云海松涛寒潭烽烟书斋白马青衫红烛黄沙"
OPEN = "天没亮,外院雾大,藏经阁的飞檐在雾里只露一个尖。他蹲到枣树底下,拿扫帚柄在湿土上划字,练气一圈,后背出了一层汗。"


def prose(seed: int, n: int = 600) -> str:
    rnd = random.Random(seed)
    return "".join("".join(rnd.choice(POOL) for _ in range(9)) + "。" for _ in range(n // 10))


def test_restaged_opening_is_rejected_but_a_new_opening_passes():
    prev, again, fresh = OPEN + prose(1), OPEN.replace("天没亮", "天没亮透") + prose(2), prose(3)
    assert opening_similarity(again, prev, []) > 0.12 and any("开场" in p for p in restage_problems(again, prev, []))
    assert restage_problems(fresh, prev, []) == []


def test_replayed_scene_is_rejected():
    scene = prose(7, 400)
    prev, replay = prose(1) + scene, prose(2) + scene
    assert phrase_overlap(replay, prev, []) > 0.06 and any("又演了一遍" in p for p in restage_problems(replay, prev, []))


def test_names_do_not_count_and_short_texts_are_skipped():
    a, b = "周小满" * 120 + prose(1, 300), "周小满" * 120 + prose(2, 300)
    assert phrase_overlap(a, b, ["周小满"]) < 0.06
    assert restage_problems("正文", "正文", []) == []            # 太短不比(篇幅检查另管)
    assert restage_problems(OPEN + prose(1), "", []) == []       # 第一章没有上一章


def test_editor_sees_how_recent_chapters_opened(conn):
    bid = repo.create_book(conn, "x")
    vid = repo.create_volume(conn, bid, 1, status="active")
    cid = repo.create_chapter(conn, bid, vid, 1, title="T1")
    repo.update_chapter(conn, cid, body=OPEN, summary="s", status="accepted")
    user = outline_messages(load_context(conn, bid))[1]["content"]
    assert "最近几章的开场:\n- 第1章:天没亮" in user and "不要再演一遍" in user
