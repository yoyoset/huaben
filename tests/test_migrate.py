import hashlib
import sqlite3

import pytest

from huaben import repo
from huaben.db import connect
from huaben.migrate import MigrationError, current_version, migrate
from huaben.migrations import MIGRATIONS
from huaben.schema import SCHEMA

ADD_COVER = "ALTER TABLE books ADD COLUMN cover TEXT NOT NULL DEFAULT '';"


def test_baseline_schema_is_frozen():
    """基线(迁移 #1)已经冻结:改它会让"新库"和"升级后的旧库"结构不一致。要改表结构就追加迁移。"""
    digest = hashlib.sha256(SCHEMA.encode("utf-8")).hexdigest()
    assert digest == "97abc2110aad8b57f33142d935d2bb6dd9247e57187f1e8ee79ca134323954ef"
    assert MIGRATIONS[0] is SCHEMA


def test_fresh_db_is_at_latest_version(tmp_path):
    conn = connect(tmp_path / "a.db")
    assert current_version(conn) == len(MIGRATIONS)
    assert migrate(conn) == len(MIGRATIONS)  # 重复调用是空操作


def test_upgrade_preserves_data_and_takes_premigrate_backup(tmp_path):
    path = tmp_path / "a.db"
    conn = connect(path)
    repo.create_book(conn, "诡仙")
    assert migrate(conn, MIGRATIONS + [ADD_COVER]) == len(MIGRATIONS) + 1
    assert conn.execute("SELECT title, cover FROM books").fetchone()[:] == ("诡仙", "")  # 数据还在,新列有默认值
    backups = list((tmp_path / "premigrate").glob("huaben-*.db"))
    assert len(backups) == 1
    old = sqlite3.connect(backups[0])
    assert old.execute("SELECT title FROM books").fetchone()[0] == "诡仙"
    assert "cover" not in [r[1] for r in old.execute("PRAGMA table_info(books)")]  # 备份是迁移前的样子
    old.close()


def test_failed_migration_rolls_back_completely(tmp_path):
    conn = connect(tmp_path / "a.db")
    repo.create_book(conn, "诡仙")
    bad = "ALTER TABLE books ADD COLUMN half_done TEXT NOT NULL DEFAULT '';\nALTER TABLE no_such_table ADD COLUMN x TEXT;"
    with pytest.raises(MigrationError, match="已回滚"):
        migrate(conn, MIGRATIONS + [bad])
    assert current_version(conn) == len(MIGRATIONS)  # 版本没动
    assert "half_done" not in [r[1] for r in conn.execute("PRAGMA table_info(books)")]  # 第一句也没留下
    assert not conn.in_transaction
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 1


def test_refuses_database_newer_than_program(tmp_path):
    path = tmp_path / "a.db"
    conn = connect(path)
    conn.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 5}")
    conn.close()
    with pytest.raises(MigrationError, match="比程序支持的"):
        connect(path)


def test_pre_migration_dev_database_is_stamped_not_rebuilt(tmp_path):
    """引入迁移之前建的开发库(user_version=0、表已存在):补盖版本戳,数据不动。"""
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.executescript(SCHEMA)
    raw.execute("INSERT INTO books(title) VALUES ('旧书')")
    raw.commit()
    assert raw.execute("PRAGMA user_version").fetchone()[0] == 0
    raw.close()
    conn = connect(path)
    assert current_version(conn) == len(MIGRATIONS)
    assert conn.execute("SELECT title FROM books").fetchone()[0] == "旧书"
    assert not (tmp_path / "premigrate").exists()  # 版本 0 的开发库不做迁移前备份(没有"迁移前的正式版本")


def test_in_memory_db_migrates_without_backup():
    conn = connect(":memory:")
    assert migrate(conn, MIGRATIONS + [ADD_COVER]) == len(MIGRATIONS) + 1  # 内存库没有文件可备份,也不应报错
