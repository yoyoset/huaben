"""启动入口:python -m huaben"""
import logging

import uvicorn

from .api.app import create_app
from .config import get_settings
from .tts.edge import EdgeTTS


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    app = create_app(settings, tts=EdgeTTS(settings.tts_voice))
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
