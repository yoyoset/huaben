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
]
