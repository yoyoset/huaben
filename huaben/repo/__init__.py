"""数据访问层:唯一的 SQL 入口。按聚合拆成子模块,对外仍以 `repo.xxx` 使用。"""
from .audio import chapters_missing_audio, get_audio, set_audio
from .books import create_book, get_bible, get_book, list_books, save_bible, update_book
from .chapters import (accepted_chapters, buffered_ahead, create_chapter, discard_unaccepted,
                       get_chapter, next_chapter_idx, recent_chapters, update_chapter)
from .ledger import (add_fact, add_foreshadow, list_characters, list_facts, list_foreshadows,
                     update_foreshadow, upsert_character)
from .runs import cost_summary, log_run
from .volumes import (active_volume, create_volume, get_volume, list_volumes, seal_volume,
                      set_volume_status)

__all__ = [
    "chapters_missing_audio", "get_audio", "set_audio",
    "create_book", "get_bible", "get_book", "list_books", "save_bible", "update_book",
    "accepted_chapters", "buffered_ahead", "create_chapter", "discard_unaccepted", "get_chapter",
    "next_chapter_idx", "recent_chapters", "update_chapter",
    "add_fact", "add_foreshadow", "list_characters", "list_facts", "list_foreshadows",
    "update_foreshadow", "upsert_character",
    "cost_summary", "log_run",
    "active_volume", "create_volume", "get_volume", "list_volumes", "seal_volume", "set_volume_status",
]
