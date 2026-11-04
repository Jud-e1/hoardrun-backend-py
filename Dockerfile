# Hoardrun API image (docs/hosting.md). Build from hoardrun-backend-py:
#   docker build -t hoardrun-api .
#   docker run -p 8000:8000 --env-file .env hoardrun-api

# ---- Build: compile wheels with the build tools, which stay out of the final image
FROM python:3.12-slim AS build
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY fintech_backend/requirements.txt /tmp/requirements.txt
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r /tmp/requirements.txt

# ---- Run
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000 \
    WEB_CONCURRENCY=2
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

WORKDIR /app
COPY fintech_backend/ .
RUN adduser --disabled-password --gecos '' --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# The slim image has no curl, so the check uses Python
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health', timeout=4)" || exit 1

# --proxy-headers: the client's real address comes from the host's load balancer
# (rate limits and signed agreements need it). Only the load balancer can reach the container.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} \
    --proxy-headers --forwarded-allow-ips="*" --timeout-keep-alive 15 --no-server-header
