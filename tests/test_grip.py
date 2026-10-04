"""章纲松紧档(T029):纯函数。最后一句要不要硬查、读感类矛盾要不要打回,都按档位分。"""
from huaben.grip import (GRIPS, MUST_PREFIX, check_ending, ending_line, grip_lines, grip_of,
                         hard_contradictions, lenient, must_block, words_of)


def test_grip_of_defaults_to_tight():
    assert grip_of({}) == "紧"
    assert grip_of({"grip": "松"}) == "松"
    assert grip_of({"grip": "随便"}) == "紧"  # 取值不认识:按"紧",老书行为不变


def test_grip_lines_by_grip():
    assert "关键章" in grip_lines({"grip": "紧"})[0]
    assert "骨架" in grip_lines({"grip": "中"})[0]
    assert "放开写" in grip_lines({"grip": "松"})[0]
    assert grip_lines({})[0] == grip_lines({"grip": "紧"})[0]


def test_grip_lines_must_and_free():
    with_must = "\n".join(grip_lines({"grip": "松", "must": ["厉九不出手"]}))
    assert "【不能错的】" in with_must and "- 厉九不出手" in with_must
    assert "【可以发挥的】斗嘴" in "\n".join(grip_lines({"grip": "松", "free": "斗嘴"}))
    assert len(grip_lines({"grip": "松"})) == 1  # must 与 free 都空:只有第一行


def test_ending_line_by_grip():
    assert "一字不改" in ending_line({"grip": "紧", "ending": "他站起来了。"})
    assert "意思到了就行" in ending_line({"grip": "中", "ending": "他站起来了。"})
    loose = ending_line({"grip": "松", "ending": "他站起来了。"})
    assert "意思到了就行" in loose and "一字不改" not in loose
    assert ending_line({"grip": "紧"}) is None
    assert ending_line({"grip": "紧", "ending": ""}) is None


def test_check_ending_only_tight():
    assert check_ending({}) is True  # 没填按"紧"
    assert check_ending({"grip": "紧"}) is True
    assert check_ending({"grip": "中"}) is False
    assert check_ending({"grip": "松"}) is False


def test_hard_contradictions_depend_on_grip():
    bad = [MUST_PREFIX + "厉九出手了", "音量没交代"]
    assert hard_contradictions({"grip": "紧"}, bad) == bad
    assert hard_contradictions({"grip": "中"}, bad) == [bad[0]]
    assert hard_contradictions({"grip": "松"}, bad) == [bad[0]]


def test_must_block_only_if_must():
    block = must_block({"must": ["厉九不出手", "不点破玉佩"]})
    assert "【本章不能错的】" in block and "- 厉九不出手" in block and "- 不点破玉佩" in block
    assert MUST_PREFIX in block
    assert must_block({}) == ""


def test_lenient_only_on_last_draft_of_looser_grips():
    """末稿放行:档位不是"紧"、是最后一稿、且总稿数大于 1(T030)。"""
    assert lenient({"grip": "中"}, 3, 3) is True
    assert lenient({"grip": "中"}, 2, 3) is False          # 不是最后一稿
    assert lenient({"grip": "紧"}, 3, 3) is False          # 紧档永不放行
    assert lenient({}, 3, 3) is False                      # 没填 = 紧
    assert lenient({"grip": "松"}, 1, 1) is False          # 只有一稿:放行等于无条件通过


def test_words_of_falls_back_to_site_default():
    assert words_of({"words": 1800}, 2500) == 1800
    assert words_of({}, 2500) == 2500
    assert words_of({"words": 0}, 2500) == 2500
