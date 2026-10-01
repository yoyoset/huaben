import sqlite3
from datetime import datetime, timedelta

import pytest

from huaben import repo
from huaben.backup import BackupError, backup_db
from huaben.db import connect


@pytest.fixture
def live_db(tmp_path):
    path = tmp_path / "huaben.db"
    conn = connect(path)
    repo.create_book(conn, "诡仙")
    conn.close()
    return path


def test_backup_is_readable_snapshot(live_db, tmp_path):
    dest = backup_db(live_db, tmp_path / "bk", now=datetime(2026, 10, 2, 3, 0, 0))
    assert dest.name == "huaben-20261002-030000.db"
    c = sqlite3.connect(dest)
    assert c.execute("SELECT title FROM books").fetchone()[0] == "诡仙"
    c.close()


def test_backup_while_writer_connection_open_in_wal_mode(live_db, tmp_path):
    """服务在写库(WAL,未 checkpoint)时备份,新数据也要在快照里 —— 直接 cp 主文件会丢。"""
    writer = connect(live_db)
    repo.create_book(writer, "夜行录")  # 在 WAL 里,主文件可能还没有
    dest = backup_db(live_db, tmp_path / "bk")
    c = sqlite3.connect(dest)
    assert {r[0] for r in c.execute("SELECT title FROM books")} == {"诡仙", "夜行录"}
    writer.close()


def test_prune_keeps_newest_n(live_db, tmp_path):
    out = tmp_path / "bk"
    t0 = datetime(2026, 10, 1)
    for i in range(5):
        backup_db(live_db, out, keep=3, now=t0 + timedelta(days=i))
    names = sorted(p.name for p in out.glob("huaben-*.db"))
    assert names == ["huaben-20261003-000000.db", "huaben-20261004-000000.db", "huaben-20261005-000000.db"]


def test_missing_db_is_explicit_error(tmp_path):
    with pytest.raises(BackupError, match="不存在"):
        backup_db(tmp_path / "nope.db", tmp_path / "bk")
    assert not (tmp_path / "bk").exists() or not list((tmp_path / "bk").glob("*.db"))


def test_corrupt_source_leaves_no_bad_backup(tmp_path):
    bad = tmp_path / "huaben.db"
    bad.write_bytes(b"this is not a sqlite database" * 100)
    with pytest.raises(BackupError):
        backup_db(bad, tmp_path / "bk")
    assert not list((tmp_path / "bk").glob("huaben-*.db"))
