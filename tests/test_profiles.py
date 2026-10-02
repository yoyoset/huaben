"""每人一个书架(profile = 人)。2026-10-02 用户要求:"我老婆是她的 profile,我是我的 profile"。"""
import sqlite3

from fastapi.testclient import TestClient

from huaben import repo
from huaben.api.app import create_app
from huaben.config import Settings
from huaben.db import connect
from huaben.migrate import migrate
from huaben.migrations import MIGRATIONS


def client(tmp_path):
    s = Settings(openrouter_api_key="x", data_dir=tmp_path, worker_enabled=False, _env_file=None)
    return TestClient(create_app(s))


def test_each_person_sees_only_their_own_shelf(tmp_path):
    c = client(tmp_path)
    me = c.post("/api/profiles", json={"name": "我"}).json()
    wife = c.post("/api/profiles", json={"name": "老婆"}).json()
    c.post("/api/books", json={"title": "夜行录", "profile_id": me["id"]})
    c.post("/api/books", json={"title": "花间集", "profile_id": wife["id"]})
    assert [b["title"] for b in c.get(f"/api/books?profile={me['id']}").json()] == ["夜行录"]
    assert [b["title"] for b in c.get(f"/api/books?profile={wife['id']}").json()] == ["花间集"]
    listed = {p["name"]: p["books"] for p in c.get("/api/profiles").json()}
    assert listed == {"我": 1, "老婆": 1}


def test_duplicate_or_missing_profile_is_a_clear_error(tmp_path):
    c = client(tmp_path)
    c.post("/api/profiles", json={"name": "我"})
    r = c.post("/api/profiles", json={"name": " 我 "})
    assert r.status_code == 409 and "已经有" in r.json()["detail"]
    assert c.get("/api/books?profile=99").status_code == 404     # 本机记着的读者已不存在 → 前端回"谁在看"
    assert c.post("/api/books", json={"title": "x", "profile_id": 99}).status_code == 404
    assert c.post("/api/profiles", json={"name": ""}).status_code == 422


def test_rename(tmp_path):
    c = client(tmp_path)
    p = c.post("/api/profiles", json={"name": "老公"}).json()
    assert c.put(f"/api/profiles/{p['id']}", json={"name": "我"}).json()["name"] == "我"


def test_upgrading_an_existing_library_keeps_every_book_on_a_default_shelf(tmp_path):
    conn = sqlite3.connect(tmp_path / "old.db")  # connect() 总会迁到最新;这里只迁到版本 6 模拟旧库
    conn.row_factory = sqlite3.Row
    migrate(conn, MIGRATIONS[:6])
    conn.execute("INSERT INTO books(title) VALUES ('旧书一'), ('旧书二')")
    conn.commit()
    migrate(conn)
    (default,) = repo.list_profiles(conn)
    assert default["name"] == "我" and default["books"] == 2
    assert {b["profile_id"] for b in repo.list_books(conn)} == {default["id"]}


def test_fresh_library_starts_with_no_profiles(tmp_path):
    conn = connect(tmp_path / "new.db")
    assert repo.list_profiles(conn) == []  # 新装:第一次打开时由读者自己建
