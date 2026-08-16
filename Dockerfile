FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HYRIVER_CACHE_NAME=/tmp/hyriver/aiohttp_cache.sqlite \
    HYRIVER_CACHE_NAME_HTTP=/tmp/hyriver/http_cache.sqlite

RUN apt-get update \
    && apt-get install --yes --no-install-recommends gdal-bin libgdal-dev \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /tmp/hyriver

WORKDIR /service

COPY pyproject.toml README.md ./
COPY app ./app
COPY notebooks ./notebooks

RUN python -m pip install --upgrade pip \
    && python -m pip install .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
