"""启动入口:python -m huaben"""
import sys

import uvicorn
from pydantic import ValidationError

from .api.app import create_app
from .config import describe_config_error, get_settings
from .logs import configure_logging
from .tts.edge import EdgeTTS


def main() -> None:
    configure_logging()
    try:
        settings = get_settings()
    except ValidationError as e:  # 配错了:说清楚哪一项、为什么,然后以非 0 退出(不打一屏堆栈)
        print(describe_config_error(e), file=sys.stderr)
        sys.exit(2)
    app = create_app(settings, tts=EdgeTTS(settings.tts_voice))
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
