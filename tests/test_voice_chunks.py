"""跨段落合并切块(chunks.py):不丢字、短对白被合并、每块不超过 ceiling、没有碎块。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pc_worker"))

from huaben_voice.chunks import chunks  # noqa: E402


def test_no_char_lost():
    t = ("第一段没有标点也很短\n"
         "“这句话是对白,带引号。”\n"
         "\n"
         + "长句子" * 60 + "。\n"
         "最后一段,收尾!")
    assert "".join(chunks(t)) == "".join(p.strip() for p in t.split("\n"))


def test_dialogue_lines_are_merged():
    t = "\n".join(["对白对白对白对”"] * 20)
    out = chunks(t)
    assert len(out) == 1


def test_every_chunk_within_ceiling():
    t = "\n".join([("他说了一句话。" * 20 if i % 3 == 0 else "短句。" * 2) for i in range(15)])
    assert all(len(c) <= 300 for c in chunks(t))


def test_no_tiny_chunk_when_mergeable():
    paras = []
    for i in range(40):
        paras.append("长段落" * 50 + "。" if i % 2 == 0 else "短。")
    out = chunks("\n".join(paras))
    assert len(out) > 1
    assert all(len(c) >= 60 for c in out)


def test_single_short_text():
    assert chunks("你好世界啊") == ["你好世界啊"]


def test_empty_text():
    assert chunks("") == []
    assert chunks("\n\n   \n") == []
