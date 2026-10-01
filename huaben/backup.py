"""数据库备份:`python -m huaben.backup --out /backups`。

- 用 SQLite 在线备份 API(`Connection.backup`),服务运行中也能得到一致的快照(库是 WAL 模式,直接 cp 文件不安全)。
- 备份完立刻对副本做 integrity_check,坏了就删掉并报错 —— 不留下"以为有备份、其实是坏的"文件。
- 只备份数据库,不备份音频:音频可由正文重新合成,体积大且无不可替代性(见 docs/deploy.md)。
- 保留最近 N 份,更早的删除。
"""
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

PREFIX = "huaben-"


class BackupError(Exception):
    pass


def backup_db(db_path: Path, out_dir: Path, keep: int = 14, now: datetime | None = None) -> Path:
    if not Path(db_path).exists():
        raise BackupError(f"数据库不存在: {db_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{PREFIX}{(now or datetime.now()):%Y%m%d-%H%M%S}.db"
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(dest))
    try:
        src.backup(dst)
        ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.Error as e:  # 源库损坏等:不能留下残缺的备份文件
        dst.close()
        src.close()
        dest.unlink(missing_ok=True)
        raise BackupError(f"备份失败: {e}") from e
    finally:
        dst.close()
        src.close()
    if ok != "ok":
        dest.unlink(missing_ok=True)
        raise BackupError(f"备份副本完整性检查失败: {ok}")
    _prune(out_dir, keep)
    return dest


def _prune(out_dir: Path, keep: int) -> None:
    files = sorted(out_dir.glob(f"{PREFIX}*.db"))  # 文件名含时间戳,字典序 = 时间序
    for old in files[:-keep] if keep > 0 else []:
        old.unlink()


def main() -> None:
    from .config import get_settings

    ap = argparse.ArgumentParser(description="备份话本数据库")
    ap.add_argument("--out", required=True, type=Path, help="备份目录")
    ap.add_argument("--keep", type=int, default=14, help="保留最近几份(默认 14)")
    args = ap.parse_args()
    dest = backup_db(get_settings().db_path, args.out, args.keep)
    print(f"备份完成: {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
