"""数据访问层:唯一的 SQL 入口。按聚合拆成子模块,对外仍以 `repo.xxx` 使用。"""
from .app_settings import get_app_settings, set_app_settings
from .audio import chapters_missing_audio, get_audio, set_audio, voiced_chapters
from .books import create_book, get_bible, get_book, list_books, open_chapter, save_bible, update_book
from .chapters import (accepted_chapters, attempt_stats, buffered_ahead, chapter_index, count_accepted,
                       create_chapter, discard_unaccepted, get_chapter, last_sealed_chapter_idx, next_chapter_idx,
                       recent_chapters, update_chapter, volume_chapter_ranges)
from .ledger import (add_fact, add_foreshadow, clear_characters, list_characters, list_facts, list_foreshadows,
                     update_foreshadow, upsert_character)
from .opening import add_message, list_messages
from .profiles import create_profile, get_profile, list_profiles, rename_profile
from .runs import cost_summary, failure_counts, log_run, recent_failures, run_totals, spent_usd, unpriced_calls
from .volumes import (active_volume, create_volume, get_volume, list_volumes, seal_volume,
                      set_volume_status)

__all__ = [
    "get_app_settings", "set_app_settings",
    "add_message", "list_messages",
    "create_profile", "get_profile", "list_profiles", "rename_profile",
    "chapters_missing_audio", "get_audio", "set_audio", "voiced_chapters",
    "create_book", "get_bible", "get_book", "list_books", "open_chapter", "save_bible", "update_book",
    "accepted_chapters", "buffered_ahead", "chapter_index", "count_accepted", "create_chapter", "discard_unaccepted", "get_chapter",
    "next_chapter_idx", "recent_chapters", "update_chapter",
    "attempt_stats", "last_sealed_chapter_idx", "volume_chapter_ranges",
    "add_fact", "add_foreshadow", "clear_characters", "list_characters", "list_facts", "list_foreshadows",
    "update_foreshadow", "upsert_character",
    "cost_summary", "failure_counts", "log_run", "recent_failures", "run_totals", "spent_usd", "unpriced_calls",
    "active_volume", "create_volume", "get_volume", "list_volumes", "seal_volume", "set_volume_status",
]
