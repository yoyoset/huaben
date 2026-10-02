"""开书服务。两个入口:
- opening_turn:读者说一句 → 向导回一句(+ 是否已问够);对话全程落库。
- finalize_book:从对话抽出故事圣经、初始化账本人物、规划第 1 卷,最后才把书置为 serializing。
  按"缺什么补什么"设计,中途失败后重试不会重复劳动,也不会留下"半开"的连载书。
"""
from .. import repo
from ..config import Settings
from ..db import tx
from ..llm import LLM
from ..pipeline.errors import ChapterFailed
from ..pipeline.llm_step import call_step
from ..pipeline.parsing import ParseError
from ..pipeline.volume import ensure_active_volume
from . import prompts
from .parsing import parse_bible, parse_guide

SAMPLE_MIN_CHARS = 200   # 读者一条消息超过这个长度,视为粘贴的样章
SAMPLE_MAX_CHARS = 1500  # 单段样章保留的上限
SAMPLE_MAX_COUNT = 3


class OpeningError(Exception):
    pass


def style_samples_from(messages: list[dict]) -> list[str]:
    """样章必须是读者原文,不能让 LLM 转述(转述就丢了文风)—— 所以确定性地从对话里取。"""
    longs = [m["content"].strip() for m in messages if m["role"] == "user" and len(m["content"].strip()) >= SAMPLE_MIN_CHARS]
    return [t[:SAMPLE_MAX_CHARS] for t in longs[:SAMPLE_MAX_COUNT]]


def transcript(messages: list[dict]) -> str:
    who = {"user": "读者", "assistant": "向导"}
    return "\n".join(f"{who[m['role']]}:{m['content']}" for m in messages)


def opening_turn(conn, llm: LLM, book_id: int, user_text: str) -> dict:
    book = repo.get_book(conn, book_id)
    if book is None:
        raise OpeningError("书不存在")
    if book["status"] != "drafting":
        raise OpeningError("这本书已经开书,不能再聊开书对话了")
    if not user_text.strip():
        raise OpeningError("消息不能为空")
    msgs = ([{"role": "system", "content": prompts.GUIDE_SYSTEM}] + repo.list_messages(conn, book_id)
            + [{"role": "user", "content": user_text}])
    res = call_step(conn, llm, book_id, None, "opening", msgs, json_mode=True, temperature=0.8, max_tokens=800)
    out = parse_guide(res.text)
    # 一问一答成对落库:调用失败时什么都不存,用户重发不会留下悬空/重复的消息
    with tx(conn):
        repo.add_message(conn, book_id, "user", user_text, commit=False)
        repo.add_message(conn, book_id, "assistant", out["reply"], commit=False)
    return {"reply": out["reply"], "ready": out["ready"]}


def _extract_bible(conn, llm: LLM, book_id: int, messages: list[dict]) -> None:
    last = ""
    for _ in range(2):
        res = call_step(conn, llm, book_id, None, "finalize", [
            {"role": "system", "content": prompts.FINALIZE_SYSTEM},
            {"role": "user", "content": prompts.finalize_user(transcript(messages))},
        ], json_mode=True, temperature=0.5)
        try:
            bible = parse_bible(res.text)
            break
        except ParseError as e:
            last = str(e)
            repo.log_run(conn, book_id, "finalize", ok=False, note=f"parse: {e}"[:300])
    else:
        raise ChapterFailed(f"定稿故事圣经两次都无法解析: {last}", step="finalize")
    core = {str(n).strip() for n in bible["core_characters"]}
    with tx(conn):  # 圣经 + 书信息 + 账本人物同一事务
        repo.update_book(conn, book_id, title=bible["title"], genre=bible["genre"],
                         synopsis=bible["synopsis"], commit=False)
        repo.save_bible(conn, book_id, world=bible["world"], style_fingerprint=bible["style_fingerprint"],
                        characters=bible["characters"], taboos=[str(t) for t in bible["taboos"]],
                        style_samples=style_samples_from(messages), extracted_msgs=len(messages), commit=False)
        repo.clear_characters(conn, book_id, commit=False)  # 重新整理时,旧圣经里的人物不能残留在账本
        for c in bible["characters"]:
            name = str(c["name"]).strip()
            repo.upsert_character(conn, book_id, name, core=name in core, commit=False)  # 角色定位留在圣经里


def finalize_book(conn, llm: LLM, settings: Settings, book_id: int) -> dict:
    book = repo.get_book(conn, book_id)
    if book is None:
        raise OpeningError("书不存在")
    if book["status"] == "serializing":
        raise OpeningError("这本书已经开书了")
    messages = repo.list_messages(conn, book_id)
    if not any(m["role"] == "user" for m in messages):
        raise OpeningError("还没有开书对话,先聊几句")
    bible = repo.get_bible(conn, book_id) or {}
    # 重试时:圣经已按全部对话整理过就跳过(不重复花钱);用户之后又补充过对话则重新整理
    if not bible.get("world") or bible.get("extracted_msgs", 0) < len(messages):
        _extract_bible(conn, llm, book_id, messages)
    ensure_active_volume(conn, llm, settings, book_id)
    repo.update_book(conn, book_id, status="serializing", gen_error="")
    return repo.get_book(conn, book_id)
