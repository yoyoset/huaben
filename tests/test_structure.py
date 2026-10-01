"""结构守卫:文件不许无限增长。超限就按职责拆,不要调高上限。"""
from pathlib import Path

MAX_LINES = 200
ROOT = Path(__file__).resolve().parent.parent


def test_source_files_stay_small():
    too_big = {}
    for f in list((ROOT / "huaben").rglob("*.py")) + list((ROOT / "tests").rglob("*.py")):
        n = len(f.read_text(encoding="utf-8").splitlines())
        if n > MAX_LINES:
            too_big[str(f.relative_to(ROOT))] = n
    assert not too_big, f"超过 {MAX_LINES} 行,请按职责拆分: {too_big}"
