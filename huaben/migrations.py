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
]
