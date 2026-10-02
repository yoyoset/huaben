"""结构守卫:文件不许无限增长。超限就按职责拆,不要调高上限。"""
import re
from pathlib import Path

MAX_LINES = 200
ROOT = Path(__file__).resolve().parent.parent


def test_source_files_stay_small():
    too_big = {}
    files = [f for d in ("huaben", "tests", "pc_worker") for f in (ROOT / d).rglob("*.py")
             if ".venv" not in f.parts]  # 电脑端程序的虚拟环境里是第三方库,不归我们管
    for pattern in ("*.js", "*.mjs", "*.css", "*.html"):  # 前端同样受限(sw.js/模块/样式)
        files += list((ROOT / "web").rglob(pattern))
    for f in files:
        n = len(f.read_text(encoding="utf-8").splitlines())
        if n > MAX_LINES:
            too_big[str(f.relative_to(ROOT))] = n
    assert not too_big, f"超过 {MAX_LINES} 行,请按职责拆分: {too_big}"


# SQL 只在 repo/(项目约定)。例外是"数据库本身"的基础设施:建连接/PRAGMA、迁移、在线备份的完整性检查。
# 此前约定只靠自觉,第四轮审查时已有 4 个业务模块各自写了查询。
SQL_INFRA = {"db.py", "migrate.py", "migrations.py", "schema.py", "backup.py"}
EXECUTE = re.compile(r"\.execute(many|script)?\(")


def test_sql_lives_only_in_repo():
    leaks = []
    for f in (ROOT / "huaben").rglob("*.py"):
        rel = f.relative_to(ROOT / "huaben")
        if rel.parts[0] == "repo" or str(rel) in SQL_INFRA:
            continue
        leaks += [f"{rel}:{i}" for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
                  if EXECUTE.search(line)]
    assert not leaks, f"SQL 应放进 huaben/repo/,业务模块调用 repo 函数: {leaks}"
