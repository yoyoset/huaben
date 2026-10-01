"""SQLite 持久层。状态集中在这里,流水线/API 只通过 Repo 读写。

用标准库 sqlite3,不上 ORM:表少、查询简单,少一层依赖。
列表类字段(节拍、知情者等)存 JSON 文本。
"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  genre TEXT NOT NULL DEFAULT '',
  synopsis TEXT NOT NULL DEFAULT '',      -- 全书梗概(分层记忆第 1 层)
  status TEXT NOT NULL DEFAULT 'drafting', -- drafting(开书中) / serializing
  read_pos INTEGER NOT NULL DEFAULT 0,     -- 读者读到第几章(缓冲区以它为基准)
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS bibles (
  book_id INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
  world TEXT NOT NULL DEFAULT '',
  characters TEXT NOT NULL DEFAULT '[]',   -- JSON: [{name, role, traits, ...}]
  style_fingerprint TEXT NOT NULL DEFAULT '',
  style_samples TEXT NOT NULL DEFAULT '[]', -- JSON: 样章片段
  taboos TEXT NOT NULL DEFAULT '[]'         -- JSON: 雷点
);
CREATE TABLE IF NOT EXISTS volumes (
  id INTEGER PRIMARY KEY,
  book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL,
  goal TEXT NOT NULL DEFAULT '',
  beats TEXT NOT NULL DEFAULT '[]',         -- JSON
  plant TEXT NOT NULL DEFAULT '[]',         -- JSON: 本卷要埋的伏笔
  resolve TEXT NOT NULL DEFAULT '[]',       -- JSON: 本卷要收的伏笔
  status TEXT NOT NULL DEFAULT 'planned',   -- planned / active / sealed
  summary TEXT NOT NULL DEFAULT '',         -- 封卷摘要
  UNIQUE(book_id, idx)
);
CREATE TABLE IF NOT EXISTS chapters (
  id INTEGER PRIMARY KEY,
  book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  volume_id INTEGER NOT NULL REFERENCES volumes(id),
  idx INTEGER NOT NULL,                     -- 全书章序号,从 1 起
  outline TEXT NOT NULL DEFAULT '',         -- 章纲(内部工单,读者不可见)
  title TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'outlined',  -- outlined / written / accepted / failed
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(book_id, idx)
);
CREATE TABLE IF NOT EXISTS ledger_characters (
  book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  alive INTEGER NOT NULL DEFAULT 1,
  location TEXT NOT NULL DEFAULT '',
  abilities TEXT NOT NULL DEFAULT '',
  relations TEXT NOT NULL DEFAULT '',
  knows TEXT NOT NULL DEFAULT '[]',         -- JSON: 此人知道的事
  core INTEGER NOT NULL DEFAULT 0,          -- 核心人物:每章都带
  updated_ch INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(book_id, name)
);
CREATE TABLE IF NOT EXISTS ledger_foreshadows (
  id INTEGER PRIMARY KEY,
  book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  planted_ch INTEGER NOT NULL,
  content TEXT NOT NULL,
  payoff_plan TEXT NOT NULL DEFAULT '',     -- 计划何时以何种方式回收
  status TEXT NOT NULL DEFAULT 'planted',   -- planted / progressing / resolved
  resolved_ch INTEGER
);
CREATE TABLE IF NOT EXISTS ledger_facts (
  id INTEGER PRIMARY KEY,
  book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  fact TEXT NOT NULL,
  established_ch INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS pipeline_runs (   -- 可观测:每步耗时/token/费用/核对结果
  id INTEGER PRIMARY KEY,
  book_id INTEGER NOT NULL,
  chapter_idx INTEGER,
  step TEXT NOT NULL,                        -- outline / write / ledger / check / tts
  duration_ms INTEGER NOT NULL DEFAULT 0,
  tokens_in INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0,
  cost_usd REAL NOT NULL DEFAULT 0,
  ok INTEGER NOT NULL DEFAULT 1,
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS audio (
  chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
  quality TEXT NOT NULL,                     -- basic(Edge) / hq(v1 PC 工人)
  path TEXT NOT NULL,
  duration_s REAL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY(chapter_id, quality)
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
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
