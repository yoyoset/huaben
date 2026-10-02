import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from huaben.api.app import create_app
from huaben.config import Settings

ROOT = Path(__file__).resolve().parent.parent


def client(tmp_path):
    s = Settings(openrouter_api_key="x", chapter_words=1, data_dir=tmp_path, worker_enabled=False, _env_file=None)
    return TestClient(create_app(s))


def test_shell_served_and_api_not_shadowed(tmp_path):
    c = client(tmp_path)
    home = c.get("/")
    assert home.status_code == 200 and "话本" in home.text and 'type="module"' in home.text
    assert c.get("/api/health").json()["ok"] is True  # 静态挂载在根,不能盖住 /api
    assert c.get("/api/books").json() == []


def test_pwa_assets_present(tmp_path):
    c = client(tmp_path)
    m = c.get("/manifest.webmanifest")
    assert m.status_code == 200 and m.json()["display"] == "standalone"
    for icon in m.json()["icons"]:  # manifest 里声明的图标必须真的存在
        assert c.get(icon["src"]).status_code == 200
    assert c.get("/icons/icon-180.png").status_code == 200  # iOS apple-touch-icon
    assert "javascript" in c.get("/sw.js").headers["content-type"]


def test_every_module_in_shell_list_exists(tmp_path):
    """sw.js 的预缓存清单里写的文件必须存在,否则 install 会整体失败、PWA 装不上。"""
    import re
    shell = re.search(r"SHELL = \[(.*?)\];", (ROOT / "web" / "sw.js").read_text(encoding="utf-8"), re.S).group(1)
    c = client(tmp_path)
    for path in re.findall(r"'(/[^']*)'", shell):
        assert c.get(path).status_code == 200, path


@pytest.mark.skipif(not shutil.which("node"), reason="需要 node 跑前端纯逻辑测试")
def test_frontend_logic_with_node():
    r = subprocess.run(["node", "--test", str(ROOT / "web" / "tests" / "logic.test.mjs")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def test_icon_only_buttons_have_accessible_names():
    """▶ ⏮ 🌙 这类纯符号按钮,读屏念不出意思:必须有 aria-label。"""
    import re
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    for tag, text in re.findall(r"(<button[^>]*>)(.*?)</button>", html):
        if not re.search(r"[\u4e00-\u9fffA-Za-z]{2,}", text):
            assert "aria-label=" in tag, tag
    assert 'id="app" tabindex="-1"' in html and 'aria-live="polite"></main>' not in html  # 不再整页播报
    assert 'id="net-banner"' in html and 'role="alert"' in html
