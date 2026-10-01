"""部署文件的静态自检。本机没有 docker,不能真正构建;这里只守住"写错了一眼能看出来"的那类问题。"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
yaml = pytest.importorskip("yaml")


def compose():
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]["huaben"]


def test_compose_keeps_secrets_out_and_data_persistent():
    svc = compose()
    assert svc["env_file"] == ".env"                      # 密钥走 .env
    assert not any("KEY" in str(v) for v in (svc.get("environment") or {}).values())  # 不把密钥写进 compose
    vols = " ".join(svc["volumes"])
    assert "./data:/data" in vols and ":/backups" in vols
    assert svc["restart"] == "unless-stopped" and "healthcheck" in svc


def test_published_port_maps_to_container_port_used_by_image():
    svc = compose()
    assert svc["ports"][0].endswith(":8000")
    assert "HUABEN_PORT=8000" in (ROOT / "Dockerfile").read_text(encoding="utf-8").replace("\\\n", " ").replace("    ", " ")


def test_dockerfile_copies_only_existing_paths_and_not_dev_deps():
    df = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for src in re.findall(r"^COPY (\S+) ", df, flags=re.M):
        assert (ROOT / src).exists(), src
    assert "requirements.txt" in df and "requirements-dev" not in df
    reqs = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "pytest" not in reqs and "edge-tts" in reqs and "httpx" in reqs  # 运行时依赖齐、测试依赖不进镜像


def test_dockerignore_excludes_secrets_and_data():
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
    assert {".env", "data", ".git"} <= set(ignored)


def test_backup_script_calls_the_backup_module():
    sh = (ROOT / "scripts" / "backup.sh").read_text(encoding="utf-8")
    assert "huaben.backup" in sh and "--out /backups" in sh and sh.startswith("#!/bin/sh")
    assert "\r" not in sh  # CRLF 会让 sh 在 Linux 上报错,必须是 LF
