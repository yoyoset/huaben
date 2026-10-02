"""前端静态文件每次用前都要向服务器确认(路线 24):否则更新后浏览器可能一直跑旧模块。"""
import pytest
from fastapi.testclient import TestClient

from huaben.api.app import create_app
from huaben.config import Settings


@pytest.fixture
def client(tmp_path):
    s = Settings(openrouter_api_key="x", data_dir=tmp_path, worker_enabled=False, _env_file=None)
    return TestClient(create_app(s))


@pytest.mark.parametrize("path", ["/", "/js/main.js", "/js/views/reader.js", "/css/app.css", "/sw.js"])
def test_shell_files_must_be_revalidated(client, path):
    r = client.get(path)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
    assert r.headers.get("etag")  # 有 ETag 才能便宜地确认(304)


def test_unchanged_file_costs_only_a_304(client):
    etag = client.get("/js/main.js").headers["etag"]
    r = client.get("/js/main.js", headers={"If-None-Match": etag})
    assert r.status_code == 304 and r.content == b""


def test_api_routes_are_not_shadowed(client):
    assert client.get("/api/health").json()["ok"] is True
