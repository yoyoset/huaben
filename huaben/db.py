"""SQLite 持久层。状态集中在这里,流水线/API 只通过 Repo 读写。

用标准库 sqlite3,不上 ORM:表少、查询简单,少一层依赖。
列表类字段(节拍、知情者等)存 JSON 文本。
"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .migrate import migrate


def connect(path: Path | str, check_same_thread: bool = True) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    migrate(conn)
    return conn


@contextmanager
def tx(conn: sqlite3.Connection):
    """显式事务:出异常整体回滚,避免半写入的账本。"""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def dumps(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def loads(s: str):
    return json.loads(s) if s else None
