"""接句工具(T018):纯函数核对 + 逐章执行 + 命令行,全部用替身,不碰网络。"""
import json

from huaben.llm import LLMResult
from huaben.smooth import SYSTEM, smooth_messages, smooth_problems, strip_punct
from huaben.smooth_run import smooth_chapter

OLD = "陈皮的血，一下子，冲上了头。木板，翻开了。" * 8  # 168 字、24 个逗号,密度约 14.3


def _r(text, **kw):
    return LLMResult(text=text, tokens_in=1, tokens_out=1, cost_usd=0, **kw)


class ScriptLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, *, max_tokens=None, temperature=0.9):
        self.calls.append(messages)
        r = self.replies.pop(0)
        return r if isinstance(r, LLMResult) else _r(r)


def test_strip_punct_ignores_punctuation():
    assert strip_punct("他的手，停了。") == strip_punct("他的手停了。")


def test_smooth_problems_checks_four_hard_rules():
    assert smooth_problems(OLD, OLD.replace("，", "", 11), []) == []  # 只去一部分逗号:字数还在 90% 以上
    changed = OLD.replace("陈皮", "木板", 1)
    assert any("改动了文字" in p for p in smooth_problems(OLD, changed, []))
    assert any("这句原话被改了" in p for p in smooth_problems("前言。" * 20 + "我不跑了。" + "后记。" * 20,
                                                              "前言。" * 20 + "后记。" * 20, ["我不跑了。"]))
    assert any("段数变了" in p for p in smooth_problems("第一段话。\n第二段话。\n第三段话。\n第四段话。",
                                                        "第一段话。第二段话。\n第三段话。第四段话。", []))
    assert any("稿子不完整" in p for p in smooth_problems(OLD, OLD[:len(OLD) // 2], []))


def test_smooth_messages_format():
    user = smooth_messages("正文", ["原话1", "原话2"], ["问题1"])[1]["content"]
    assert smooth_messages("正文", ["原话1"], [])[0]["content"] == SYSTEM
    assert "不许动的原话:\n- 原话1\n- 原话2" in user and "上一稿的问题" in user and "下面是要改的正文" in user
    plain = smooth_messages("正文", [], [])[1]["content"]
    assert "不许动的原话" not in plain and "上一稿的问题" not in plain


def test_low_density_skips_the_model():
    llm = ScriptLLM([])
    r = smooth_chapter(llm, "陈皮的血一下子冲上了头。木板翻开了。", [])
    assert r["status"] == "ok" and r["tries"] == 0 and llm.calls == []


def test_first_try_ok():
    good = OLD.replace("，", "", 11)  # 密度 8.3,字数 93%
    r = smooth_chapter(ScriptLLM([good]), OLD, [])
    assert r["status"] == "ok" and r["tries"] == 1 and r["text"] == good


def test_word_change_then_ok():
    bad = OLD.replace("陈皮", "木板", 1)
    good = OLD.replace("，", "", 11)
    llm = ScriptLLM([bad, good])
    r = smooth_chapter(llm, OLD, [])
    assert r["status"] == "ok" and r["tries"] == 2
    assert "改动了文字" in llm.calls[1][-1]["content"]  # 第二次带着第一稿的问题
    assert all(c[-1]["content"].endswith(OLD) for c in llm.calls)  # 每次都从原稿改


def test_still_choppy_returns_the_best():
    v1 = OLD.replace("，", "", 2)  # 13.1
    v2 = OLD.replace("，", "", 4)  # 11.9,最低
    v3 = OLD.replace("，", "", 3)  # 12.5
    r = smooth_chapter(ScriptLLM([v1, v2, v3]), OLD, [])
    assert r["status"] == "still_choppy" and r["text"] == v2 and r["tries"] == 3


def test_all_hard_problems_keeps_original():
    bad = OLD.replace("陈皮", "木板", 1)
    r = smooth_chapter(ScriptLLM([bad, bad, bad]), OLD, [])
    assert r["status"] == "kept_original" and r["text"] == OLD and r["tries"] == 3


def test_cli_copies_out_of_range_and_writes_report(tmp_path, monkeypatch):
    import huaben.smooth_cli as cli
    src = tmp_path / "src"
    src.mkdir()
    (src / "01.txt").write_text("陈皮的血，一下子，冲上了头。" * 30, encoding="utf-8")
    (src / "02.txt").write_text("已经接顺的正文。木板翻开了。", encoding="utf-8")
    vol = tmp_path / "vol.json"
    vol.write_text(json.dumps({"chapters": [{"lines": []}, {"lines": []}]}, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(cli, "build_client", lambda: ScriptLLM([("陈皮的血，一下子，冲上了头。" * 30).replace("，", "", 27)]))
    assert cli.main(["--src", str(src), "--out", str(out), "--volume", str(vol), "--from", "1", "--to", "1"]) == 0
    assert (out / "02.txt").read_text(encoding="utf-8") == "已经接顺的正文。木板翻开了。"  # 范围外原样复制
    assert "一下子冲上了头" in (out / "01.txt").read_text(encoding="utf-8")  # 范围内写了新稿
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert len(report) == 1 and report[0]["status"] == "ok"


def test_cli_refuses_same_src_and_out(tmp_path, monkeypatch):
    import huaben.smooth_cli as cli
    src = tmp_path / "src"
    src.mkdir()
    (src / "01.txt").write_text("正文。", encoding="utf-8")
    vol = tmp_path / "vol.json"
    vol.write_text(json.dumps({"chapters": []}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(cli, "build_client", lambda: ScriptLLM([]))
    assert cli.main(["--src", str(src), "--out", str(src), "--volume", str(vol)]) != 0
    assert not (src / "report.json").exists()  # 什么都不写
