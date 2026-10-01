"""数据库迁移:用 `PRAGMA user_version` 记版本,按序执行 migrations.MIGRATIONS。

规则:
- 版本号 = 已执行的迁移条数。新库从 0 一路跑到最新;旧库只跑缺的。
- 每条迁移在**一个事务**里执行(含 user_version 的更新):失败则整体回滚,版本不变,库不会停在半截。
- 有数据的旧库迁移前先做一份备份(`<数据目录>/premigrate/`),迁移失败/结果不对还能退回。
- 程序比库旧(库版本 > 程序已知最新)→ 拒绝启动,不拿旧代码去读新结构。
"""
import sqlite3
from pathlib import Path

from .backup import backup_db
from .migrations import MIGRATIONS


class MigrationError(Exception):
    pass


def current_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _db_file(conn: sqlite3.Connection) -> Path | None:
    row = conn.execute("PRAGMA database_list").fetchone()
    return Path(row[2]) if row[2] else None  # 内存库没有文件


def _has_user_data(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0] > 0


def migrate(conn: sqlite3.Connection, migrations: list[str] | None = None) -> int:
    """把库迁到最新,返回最终版本号。"""
    migrations = MIGRATIONS if migrations is None else migrations
    start = current_version(conn)
    latest = len(migrations)
    if start > latest:
        raise MigrationError(f"数据库版本 {start} 比程序支持的 {latest} 新,请升级程序,不要用旧版本打开新库")
    if start == latest:
        return start
    path = _db_file(conn)
    if path is not None and start > 0 and _has_user_data(conn):
        backup_db(path, path.parent / "premigrate", keep=5)
    for version in range(start + 1, latest + 1):
        sql = migrations[version - 1]
        try:
            # executescript 自带"先提交再执行",所以事务边界必须写在脚本里
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {version};\nCOMMIT;")
        except sqlite3.Error as e:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise MigrationError(f"迁移到版本 {version} 失败(已回滚,库仍在版本 {version - 1}): {e}") from e
    return latest
