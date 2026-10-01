"""SQLite 基线表结构 = 迁移 #1。**已冻结,不要再改**:改表结构请在 migrations.py 末尾追加迁移(测试钉住了本文件的哈希)。"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  genre TEXT NOT NULL DEFAULT '',
  synopsis TEXT NOT NULL DEFAULT '',      -- 全书梗概(分层记忆第 1 层)
  status TEXT NOT NULL DEFAULT 'drafting', -- drafting(开书中) / serializing
  read_pos INTEGER NOT NULL DEFAULT 0,     -- 读者读到第几章(缓冲区以它为基准)
  gen_error TEXT NOT NULL DEFAULT '',      -- 后台生成最近一次失败的人话摘要;成功即清空,界面据此提示
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
  target_chapters INTEGER NOT NULL DEFAULT 30,  -- 计划章数,写满即封卷
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
CREATE TABLE IF NOT EXISTS opening_messages (  -- 开书对话记录
  id INTEGER PRIMARY KEY,
  book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  role TEXT NOT NULL,                        -- user / assistant
  content TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
