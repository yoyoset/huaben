"""配音的先后与每轮上限(路线 17)。

复现场景:恢复备份后 30 章音频都要重配,读者停在第 25 章。此前一轮会从第 1 章配到第 30 章才放锁。
"""
from huaben import repo
from huaben.config import Settings
from huaben.llm_fake import FakeLLM
from huaben.scheduler import top_up
from huaben.tts.fake import FakeTTS
from huaben.tts.service import audio_round_limit, listening_order


def book_with_chapters(conn, n, at):
    bid = repo.create_book(conn, "书")
    repo.update_book(conn, bid, status="serializing", read_pos=at, last_opened=at)
    vid = repo.create_volume(conn, bid, 1, status="active", target_chapters=100)
    for i in range(1, n + 1):
        cid = repo.create_chapter(conn, bid, vid, i, title=f"T{i}")
        repo.update_chapter(conn, cid, body=f"正文{i}。", summary="s", status="accepted")
    return bid


def voiced_order(tts):
    return [int(c.split("章")[0].removeprefix("第")) for c in tts.calls]


def test_listening_order_puts_what_is_heard_next_first():
    chs = [{"idx": i} for i in range(1, 8)]
    assert [c["idx"] for c in listening_order(chs, 4)] == [4, 5, 6, 7, 3, 2, 1]
    assert [c["idx"] for c in listening_order(chs, 0)] == [1, 2, 3, 4, 5, 6, 7]  # 还没读过:从头
    assert listening_order([], 3) == []


def test_round_voices_from_reading_position_and_stops_at_limit(conn, tmp_path):
    s = Settings(openrouter_api_key="x", chapter_words=1, buffer_chapters=3, data_dir=tmp_path, _env_file=None)
    bid = book_with_chapters(conn, 30, at=25)
    tts = FakeTTS()
    res = top_up(conn, FakeLLM([]), s, bid, tts=tts)  # 缓冲已满(25 之后还有 5 章):不写文字
    limit = audio_round_limit(s)
    assert voiced_order(tts) == [25, 26, 27, 28][:limit]
    assert res.audio_error == ""  # 没配完不是错误,下一轮接着配
    top_up(conn, FakeLLM([]), s, bid, tts=tts)
    assert voiced_order(tts)[limit:2 * limit] == [29, 30, 24, 23][:limit]  # 先补完往后的,再往回补


class RecordingTTS(FakeTTS):
    """记下每次合成时模型已被调用了几次,用来判断配音与写章的先后。"""

    def __init__(self, llm, **kw):
        super().__init__(**kw)
        self.llm, self.llm_calls_at = llm, []

    def synthesize(self, text):
        self.llm_calls_at.append(len(self.llm.calls))
        return super().synthesize(text)


def test_new_book_first_chapter_is_voiced_before_the_rest_are_written(conn, tmp_path):
    from test_scheduler import PLAN, chapter_replies, serializing_book
    s = Settings(openrouter_api_key="x", chapter_words=1, buffer_chapters=3, data_dir=tmp_path, _env_file=None)
    bid = serializing_book(conn)
    llm = FakeLLM([PLAN] + chapter_replies(3))
    tts = RecordingTTS(llm)
    res = top_up(conn, llm, s, bid, tts=tts)
    assert res.generated == 3 and voiced_order(tts) == [1, 2, 3]
    # 卷规划 1 次 + 每章 3 次(章纲/正文/入账):第 1 章在第 4 次调用后就配音,而不是等 10 次全写完
    assert tts.llm_calls_at == [4, 7, 10]


def test_voicing_failure_mid_round_does_not_stop_text(conn, tmp_path):
    from test_scheduler import PLAN, chapter_replies, serializing_book
    s = Settings(openrouter_api_key="x", chapter_words=1, buffer_chapters=3, data_dir=tmp_path,
                 tts_retries=0, _env_file=None)
    bid = serializing_book(conn)
    tts = FakeTTS(always_fail=True)
    res = top_up(conn, FakeLLM([PLAN] + chapter_replies(3)), s, bid, tts=tts)
    assert res.generated == 3 and "配音失败" in res.audio_error
    assert len(tts.calls) == 1  # 失败后本轮不再反复尝试,留给配音退避


def test_round_limit_covers_a_full_buffer_plus_current_chapter():
    s = Settings(openrouter_api_key="x", chapter_words=1, buffer_chapters=3, _env_file=None)
    assert audio_round_limit(s) == 4  # 正常连载时一轮最多新增"缓冲章数"章 + 正在听的这章,不会被上限拖慢
