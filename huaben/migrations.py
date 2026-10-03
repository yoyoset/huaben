"""迁移清单。第 N 条 = 把库从版本 N-1 升到版本 N 的 SQL。

**铁律:已发布的条目永远不改**(含第 1 条的基线 schema.SCHEMA —— 有测试钉住它的哈希)。
要改表结构,在列表末尾**追加**新条目,例如:

    "ALTER TABLE books ADD COLUMN cover TEXT NOT NULL DEFAULT '';",

追加后同步更新 docs/architecture.md 的数据模型描述。SQLite 加列用 ALTER TABLE ADD COLUMN(须带 DEFAULT);
删列/改类型要走"建新表 → 拷数据 → 删旧表 → 改名"。
"""
from .schema import SCHEMA

MIGRATIONS: list[str] = [
    SCHEMA,  # 1: 基线(2026-10-02 开发期累积的全部表结构;此前没有部署过,无历史库需要兼容)
    # 2: 世界设定定本。封卷时把本卷新确立的事实并入,之后 prompt 带定本 + 本卷事实,不再按条数截断丢掉最早的事实
    "ALTER TABLE bibles ADD COLUMN canon TEXT NOT NULL DEFAULT '';",
    # 3: 圣经是根据前多少条开书对话整理的。开书失败后用户又补充了对话,重试时据此重新整理,而不是沿用旧圣经
    "ALTER TABLE bibles ADD COLUMN extracted_msgs INTEGER NOT NULL DEFAULT 0;",
    # 4: 最后打开的章(续读位置)。read_pos 从此只表示"读到的最远章",只增不减,预生成缓冲以它为准;
    #    翻回前面重读只改 last_opened,不会让缓冲误以为读者退回去了
    "ALTER TABLE books ADD COLUMN last_opened INTEGER NOT NULL DEFAULT 0;",
    # 5: 人物人设(身份/性格/说话方式)。中途登场的配角不在开书圣经的人物卡里,没有人设就会反复出场时漂移
    "ALTER TABLE ledger_characters ADD COLUMN profile TEXT NOT NULL DEFAULT '';",
    # 6: 配音错误单独存。此前与文字错误共用 gen_error:一轮只配音不写文字时会把文字错误清掉,反之亦然
    "ALTER TABLE books ADD COLUMN audio_error TEXT NOT NULL DEFAULT '';",
    # 7: 每人一个书架(2026-10-02 用户要求:"我老婆是她的 profile,我是我的 profile")。profile = 人,不要密码;
    #    已有的书归到默认的"我",升级不丢书
    """CREATE TABLE profiles (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
ALTER TABLE books ADD COLUMN profile_id INTEGER REFERENCES profiles(id);
INSERT INTO profiles(name) SELECT '我' WHERE EXISTS (SELECT 1 FROM books);
UPDATE books SET profile_id = (SELECT id FROM profiles WHERE name = '我') WHERE profile_id IS NULL;""",
    # 8: 网页"设置"页保存的配置(模型接口地址/密钥/模型名等)。用户要能在网页里填密钥、以后换成 OpenCode 的 key,
    #    不必登录服务器改 .env。这里的值优先于环境变量;没填的项沿用 .env
    """CREATE TABLE app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);""",
    # 9: 伏笔分大小 short / medium / long(2026-10-02 用户:伏笔太死,有的该很短、有的该很长)。
    #    已有的伏笔按中线(本卷内收)处理,见 foreshadow_scale.py
    "ALTER TABLE ledger_foreshadows ADD COLUMN scale TEXT NOT NULL DEFAULT 'medium';",
    # 10: 电脑版音频是哪个音色配的(引擎:音色)。2026-10-02 用户嫌 Kokoro 音色差、换成 Qwen3-TTS:
    #     没有这一列,已经配过的章永远不会换新音色。旧记录为空 = 未知音色
    "ALTER TABLE audio ADD COLUMN voice TEXT NOT NULL DEFAULT '';",
    # 11: 每本书的写法设定(叙事结构/文笔/伏笔布局/节奏/补充要求,JSON)。2026-10-03 用户:开书时要给模板选,
    #     不然叙事方式、伏笔长度这些基础的东西读者想不到去提。旧书为空 = 默认,见 craft.py
    "ALTER TABLE books ADD COLUMN craft TEXT NOT NULL DEFAULT '';",
    # 12: 出门前"预备到第几章"(2026-10-03 用户:跑步前下好 10 章、20 章离线听)。0 = 没有预备,按默认缓冲,见 prep.py
    "ALTER TABLE books ADD COLUMN prep_until INTEGER NOT NULL DEFAULT 0;",
    # 13: 卷的征战结构(对手与道理/赌注/打法/谷底/代价/变化/推进的长线,JSON)。2026-10-03 用户:吸引人的连载
    #     就是一段段征战;旧卷为空,进行中的卷在下一次写章前自动补全,见 arc.py
    "ALTER TABLE volumes ADD COLUMN arc TEXT NOT NULL DEFAULT '{}';",
    # 14: 本章用来推动情节/制造悬念的手段(JSON 列表,入账时登记)。2026-10-03 实测《算尽仙朝》10 章章章"残片发烫",
    #     《杂役仙尊》14 章里 12 章靠"枕下纸条"——规划下一章时据此点名"别再用",见 devices.py
    "ALTER TABLE chapters ADD COLUMN devices TEXT NOT NULL DEFAULT '[]';",
    # 15: 角色的招牌能力与成长阶段(JSON)。2026-10-03 用户:要能写出《海贼王》《火影》《死神》那种故事——
    #     那三部里每个重要角色都有招牌能力(恶魔果实/忍术/斩魄刀),有名字与规则、随剧情进阶。旧数据为空,见 signature.py
    "ALTER TABLE ledger_characters ADD COLUMN signature TEXT NOT NULL DEFAULT '{}';",
    # 16: 热路径索引(路线 63)。此前一张索引都没有:书架每本书计数、缓冲判断、封卷范围、花费汇总
    #     都在全表扫描;几千章时明显变慢。SQLite 只自动为 PK/UNIQUE 建索引,其余要显式加。
    "CREATE INDEX IF NOT EXISTS idx_chapters_book_status ON chapters(book_id, status);"
    "CREATE INDEX IF NOT EXISTS idx_chapters_book_status_idx ON chapters(book_id, status, idx);"
    "CREATE INDEX IF NOT EXISTS idx_runs_book_created ON pipeline_runs(book_id, created_at);"
    "CREATE INDEX IF NOT EXISTS idx_foreshadows_book_status ON ledger_foreshadows(book_id, status);"
    "CREATE INDEX IF NOT EXISTS idx_facts_book_ch ON ledger_facts(book_id, established_ch);"
    "CREATE INDEX IF NOT EXISTS idx_messages_book ON opening_messages(book_id, id);"
    "CREATE INDEX IF NOT EXISTS idx_audio_chapter ON audio(chapter_id);",
    # 17: 故事的主题与核心谜团(路线 69)。2026-10-03 用户:要能写出《海贼王》《火影》《死神》那种故事——
    #     它们的长线最后都指向一个"这本书到底在讲什么"的核心。旧书为空,不影响;见 theme.py
    "ALTER TABLE bibles ADD COLUMN theme TEXT NOT NULL DEFAULT '';"
    "ALTER TABLE bibles ADD COLUMN central_mystery TEXT NOT NULL DEFAULT '';",
    # 18: 每个节拍分配几章(JSON 整数列表,与 beats 等长)。2026-10-03 用户:"都四章了,连山门都还没进"——
    #     旧的平均摊法让小过渡也占 3 章、重头戏被压扁。旧卷为空 = 走原来的平均算法,补预算见 T004,见 beat_budget.py
    "ALTER TABLE volumes ADD COLUMN beat_chapters TEXT NOT NULL DEFAULT '[]';",
    # 19: 剧本制(T010)。scripted=1 表示这本书的章纲与卷规划只来自架构方导入的剧本,不让模型现出;
    #     secrets=真相层(只有作者知道的答案),只存不用:不进任何模型提示词,也不进任何读者接口,见 architecture.md 5.5
    "ALTER TABLE books ADD COLUMN scripted INTEGER NOT NULL DEFAULT 0;"
    "ALTER TABLE bibles ADD COLUMN secrets TEXT NOT NULL DEFAULT '';",
    # 20: 剧本制(T011)。scripted_outlines = 架构方预先写好的章纲(含节奏标记,原样存);ledger_foreshadows.key = 伏笔代号
    #     (如 F3)。章纲提前写好,而伏笔的数据库编号要等写到埋它的那一章才产生,所以章纲里只能用代号引用它
    """CREATE TABLE scripted_outlines (
  book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL,
  outline TEXT NOT NULL,
  PRIMARY KEY(book_id, idx)
);
ALTER TABLE ledger_foreshadows ADD COLUMN key TEXT NOT NULL DEFAULT '';""",
    # 21: 剧本制(T016)。scripted_bodies = 架构方写好的正文(有它的章不用作者模型,直接记账)
    """CREATE TABLE scripted_bodies (
  book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL,
  body TEXT NOT NULL,
  PRIMARY KEY(book_id, idx)
);""",
]
