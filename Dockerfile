FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HUABEN_DATA_DIR=/data \
    HUABEN_HOST=0.0.0.0 \
    HUABEN_PORT=8000

WORKDIR /app

# 依赖层单独缓存:只改代码时不重装依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY huaben ./huaben
COPY web ./web

VOLUME ["/data"]
EXPOSE 8000

# 不依赖 curl:用标准库探活
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["python", "-m", "huaben"]
