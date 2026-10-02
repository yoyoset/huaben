"""启动:python -m huaben_voice --server http://10.1.1.13:8210 [--token ...] [--engine fake]"""
import argparse
import logging
import os

from .client import VoiceClient
from .engines import ENGINES, create_engine
from .loop import run_forever


def main() -> None:
    ap = argparse.ArgumentParser(prog="huaben_voice", description="话本配音程序(电脑端)")
    ap.add_argument("--server", default=os.environ.get("HUABEN_SERVER", ""), help="话本服务器地址,如 http://10.1.1.13:8210")
    ap.add_argument("--token", default=os.environ.get("HUABEN_VOICE_WORKER_TOKEN", ""), help="服务器设了令牌时必填")
    ap.add_argument("--engine", default="fake", choices=sorted(ENGINES), help="TTS 引擎")
    ap.add_argument("--idle", type=float, default=30.0, help="没任务时隔多少秒再问")
    args = ap.parse_args()
    if not args.server:
        ap.error("需要 --server(或环境变量 HUABEN_SERVER)")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    run_forever(VoiceClient.connect(args.server, args.token), create_engine(args.engine), idle_s=args.idle)


if __name__ == "__main__":
    main()
