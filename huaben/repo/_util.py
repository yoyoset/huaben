"""仓库层内部小工具。"""
import sqlite3


def row(r: sqlite3.Row | None) -> dict | None:
    return dict(r) if r is not None else None
