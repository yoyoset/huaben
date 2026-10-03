"""同一章里逐字重复的长片段(路线 57)。只提醒、不打回(分不清复沓与词穷)。"""
from huaben.context import load_context
from huaben.pipeline.prompts import ledger_messages, outline_messages, write_messages
from huaben.repetition import PHRASE_N, repeated_phrases, repetition_note
from huaben import repo

OUTLINE = {"title": "T", "outline": "事", "characters": [], "foreshadows": [], "planned_reversals": [], "hook": "钩"}


def test_flags_long_phrase_repeated_three_times():
    line = "他笑得像被雨打过的狗尾巴草一样"
    body = ("开场。" + line + "中间发生的别的事,写了很多很多字来拉开距离。" * 3 + line + "又过了很久。" + line)
    hits = repeated_phrases(body, [])
    assert any(g in line for g in hits)          # 命中的代表片段落在重复句里
    assert PHRASE_N == 12                        # 短于此命中率太高(实测 8 字 25/31 章)
    assert repetition_note(body, []).startswith("本章有逐字重复的长片段:")


def test_two_times_is_not_flagged():
    """只重复两次不算(可能是呼应):机械检查宁漏不误伤。"""
    line = "他笑得像被雨打过的狗尾巴草一样"
    filler = ("于是众人各自散去。天色将晚,他这才收拾停当。风从巷口灌进来,卷起一层薄灰。"
              "檐下的灯笼晃了晃,灯芯爆了个火花。远处打更的声音传过来,不紧不慢。")  # 各不相同,不构成重复
    body = "开头。" + line + filler + line + "结尾。"
    assert repeated_phrases(body, []) == [] and repetition_note(body, []) == ""


def test_names_are_excluded():
    """含人名的片段不算:主角名字每章都出现,不代表重复。"""
    body = "周小满把这件事记在心里,周小满又想了想,周小满还是决定先不动,周小满站起身。"
    assert repeated_phrases(body, ["周小满"], n=5, k=3) == []


def test_prompts_ask_not_to_repeat_and_editor_to_note(conn):
    bid = repo.create_book(conn, "书")
    repo.create_volume(conn, bid, 1, status="active")
    ctx = load_context(conn, bid)
    assert "不要逐字重复" in write_messages(ctx, OUTLINE, 1000)[1]["content"]
    assert "不要逐字重复" in outline_messages(ctx)[1]["content"]
    ledger = ledger_messages(ctx, OUTLINE, "正文")[1]["content"]
    assert "逐字重复的比喻" in ledger
    from huaben.pipeline.prompts import LEDGER_SCHEMA
    assert "逐字重复的比喻" in LEDGER_SCHEMA
