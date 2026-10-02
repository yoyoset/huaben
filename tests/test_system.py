"""/api/health:探活 + 排查信息,不泄露密钥。"""
import time

from fastapi.testclient import TestClient

from huaben import __version__
from huaben.api.app import create_app
from huaben.config import Settings
from huaben.migrations import MIGRATIONS


def test_health_reports_versions_and_config_without_secret(tmp_path):
    s = Settings(openrouter_api_key="sk-secret-123", data_dir=tmp_path, worker_enabled=False, _env_file=None)
    r = TestClient(create_app(s)).get("/api/health")
    body = r.json()
    assert r.status_code == 200 and body["ok"] is True and body["version"] == __version__
    assert body["db"] == {"version": len(MIGRATIONS), "latest": len(MIGRATIONS)}
    assert body["worker"] == {"enabled": False}
    assert body["llm"] == {"configured": True, "model": s.llm_model, "base_url": s.openrouter_base_url}
    assert "sk-secret-123" not in r.text  # 只报告配没配,不回显密钥


def test_health_is_200_even_without_llm_key(tmp_path):
    """没配密钥不算"服务挂了"(否则 docker 会反复重启),但要如实报告。"""
    s = Settings(openrouter_api_key="", data_dir=tmp_path, worker_enabled=False, _env_file=None)
    r = TestClient(create_app(s)).get("/api/health")
    assert r.status_code == 200 and r.json()["llm"]["configured"] is False


def test_health_shows_running_worker(tmp_path):
    s = Settings(openrouter_api_key="", data_dir=tmp_path, worker_enabled=True, worker_interval_s=0.05,
                 _env_file=None)
    with TestClient(create_app(s)) as c:
        deadline = time.time() + 3
        while time.time() < deadline and not c.get("/api/health").json()["worker"]["ticks"]:
            time.sleep(0.05)
        w = c.get("/api/health").json()["worker"]
    assert w["enabled"] and w["running"] and w["ticks"] >= 1 and w["last_tick_at"]
