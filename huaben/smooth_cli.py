"""命令行:把一个目录里的切碎正文逐章接顺。绝不写回 --src;--out 与 --src 是同一个目录就报错退出。

用法:python -m huaben.smooth_cli --src <目录> --out <目录> --volume <vol.json> [--from 12] [--to 30]
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from .smooth_run import smooth_chapter


def build_client():
    """真实的模型客户端(测试里用替身替掉)。配置走网页"设置"优先、.env 兜底的那一套。"""
    from types import SimpleNamespace

    from .api.deps import llm_settings
    from .config import get_settings
    from .llm import OpenRouterClient
    return OpenRouterClient(llm_settings(SimpleNamespace(settings=get_settings())))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="把切碎的正文逐章接顺(一章一次调用)")
    ap.add_argument("--src", required=True, help="原稿目录,里面的 NN.txt 逐个读")
    ap.add_argument("--out", required=True, help="改稿写到这里(UTF-8,末尾一个换行)")
    ap.add_argument("--volume", required=True, help="卷剧本 json,第 N 章的原话取 chapters[N-1][lines]")
    ap.add_argument("--from", dest="from_idx", type=int, default=None, help="从第几章开始改")
    ap.add_argument("--to", dest="to_idx", type=int, default=None, help="改到第几章")
    a = ap.parse_args(argv)
    src, out = Path(a.src), Path(a.out)
    if src.resolve() == out.resolve():
        print("--out 不能和 --src 是同一个目录:改稿绝不写回原稿", file=sys.stderr)
        return 2
    chapters = json.loads(Path(a.volume).read_text(encoding="utf-8")).get("chapters") or []
    llm = build_client()
    out.mkdir(parents=True, exist_ok=True)
    report = []
    for p in sorted(src.glob("[0-9][0-9].txt")):
        n = int(p.stem)
        if (a.from_idx is not None and n < a.from_idx) or (a.to_idx is not None and n > a.to_idx):
            shutil.copyfile(p, out / p.name)
            continue
        body = p.read_text(encoding="utf-8")
        ch = chapters[n - 1] if 1 <= n <= len(chapters) else {}
        r = smooth_chapter(llm, body, ch.get("lines") or [])
        (out / p.name).write_text(r["text"].rstrip("\n") + "\n", encoding="utf-8")
        print(f"{n:02d} {r['status']} {r['before']:.1f}->{r['after']:.1f} tries={r['tries']}")
        report.append({"chapter": n, "status": r["status"], "before": r["before"], "after": r["after"],
                       "tries": r["tries"], "notes": r["notes"]})
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
