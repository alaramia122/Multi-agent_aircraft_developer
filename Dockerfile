FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/gateway

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
COPY profiles ./profiles

RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && python -m pip install strictdoc==0.30.0 \
    && useradd --create-home --uid 10001 gateway \
    && chown -R gateway:gateway /srv/gateway

USER gateway

EXPOSE 8000

CMD ["uvicorn", "engineering_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
