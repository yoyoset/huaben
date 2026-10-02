"""目录按段取:几千章的书,阅读页/播放器只取当前章前后,目录页按页取(2026-10-02 用户:章节多了目录会卡死)。"""
from test_voice_api import setup


def test_chapter_list_can_be_fetched_by_range(tmp_path):
    s, conn, (a, b), c = setup(tmp_path)  # 甲 3 章
    idxs = lambda q="": [x["idx"] for x in c.get(f"/api/books/{a}/chapters{q}").json()]  # noqa: E731
    assert idxs() == [1, 2, 3]                       # 不带参数:全部(兼容旧调用)
    assert idxs("?from=2&to=3") == [2, 3]
    assert idxs("?from=1&to=1") == [1]
    assert idxs("?from=3") == [3] and idxs("?to=2") == [1, 2]
    assert idxs("?from=10&to=20") == []              # 超出范围:空,不报错
    assert c.get(f"/api/books/{a}/chapters?from=0").status_code == 422
