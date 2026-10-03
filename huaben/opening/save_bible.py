"""把一份已解析的故事圣经写进数据库:书信息 + 圣经 + 账本人物,同一事务。
从开书定稿里拆出来,让"开书对话定稿"和"剧本制导入"共用同一段落库逻辑(见 T010)。
"""
from .. import repo
from ..db import tx
from ..signature import normalize_signature


def save_parsed_bible(conn, book_id: int, bible: dict, style_samples: list[str], extracted_msgs: int = 0,
                      secrets: str = "") -> None:
    core = {str(n).strip() for n in bible["core_characters"]}
    with tx(conn):  # 圣经 + 书信息 + 账本人物同一事务
        repo.update_book(conn, book_id, title=bible["title"], genre=bible["genre"],
                         synopsis=bible["synopsis"], commit=False)
        repo.save_bible(conn, book_id, world=bible["world"], style_fingerprint=bible["style_fingerprint"],
                        characters=bible["characters"], taboos=[str(t) for t in bible["taboos"]],
                        theme=str(bible.get("theme") or ""), central_mystery=str(bible.get("central_mystery") or ""),
                        style_samples=style_samples, extracted_msgs=extracted_msgs, secrets=secrets, commit=False)
        repo.clear_characters(conn, book_id, commit=False)  # 重新整理时,旧圣经里的人物不能残留在账本
        for c in bible["characters"]:
            name = str(c["name"]).strip()
            profile = " ".join(str(c.get(k, "")).strip() for k in ("role", "traits")).strip()
            sig = normalize_signature(c.get("signature"))
            repo.upsert_character(conn, book_id, name, core=name in core, profile=profile, commit=False,
                                  signature=sig)
