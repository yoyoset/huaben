"""启动:python -m huaben_voice --server http://10.1.1.13:8210 --engine qwen3-zh [--voice Uncle_Fu] [--instruct ...] [--token ...]"""
import argparse
import hashlib
import logging
import os

from .client import VoiceClient
from .engines import ENGINES, create_engine
from .loop import run_forever


def voice_id(engine: str, voice: str, instruct: str = "") -> str:
    """报给服务器的"这是哪种声音":引擎、音色、朗读指令任一变了,都算新音色(读者还没听的章会换成新的)。"""
    tag = f":{hashlib.sha1(instruct.encode()).hexdigest()[:6]}" if instruct else ""
    return f"{engine}:{voice}{tag}"[:120]


def main() -> None:
    ap = argparse.ArgumentParser(prog="huaben_voice", description="话本配音程序(电脑端)")
    ap.add_argument("--server", default=os.environ.get("HUABEN_SERVER", ""), help="话本服务器地址,如 http://10.1.1.13:8210")
    ap.add_argument("--token", default=os.environ.get("HUABEN_VOICE_WORKER_TOKEN", ""), help="服务器设了令牌时必填")
    ap.add_argument("--engine", default="fake", choices=sorted(ENGINES), help="TTS 引擎")
    ap.add_argument("--voice", default="zf_001", help="音色(kokoro-zh:zf_xxx 女声 / zm_xxx 男声)")
    ap.add_argument("--speed", type=float, default=1.0, help="语速倍率")
    ap.add_argument("--instruct", default="", help="qwen3-zh:朗读语气指令,如\"像说书人一样娓娓道来\"")
    ap.add_argument("--idle", type=float, default=30.0, help="没任务时隔多少秒再问")
    args = ap.parse_args()
    if not args.server:
        ap.error("需要 --server(或环境变量 HUABEN_SERVER)")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # 否则每次轮询都打一行,淹没"第 N 章配好"
    log = logging.getLogger("huaben_voice")
    log.info("加载引擎 %s(音色 %s)……首次运行会下载模型", args.engine, args.voice)
    opts = {"voice": args.voice, "speed": args.speed, **({"instruct": args.instruct} if args.instruct else {})}
    engine = create_engine(args.engine, **opts)
    log.info("引擎就绪,开始向 %s 取配音任务", args.server)
    run_forever(VoiceClient.connect(args.server, args.token), engine, idle_s=args.idle,
                voice=voice_id(args.engine, args.voice, args.instruct))


if __name__ == "__main__":
    main()
