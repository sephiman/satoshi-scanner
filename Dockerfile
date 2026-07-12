FROM python:3.14-slim

# 3.13 (not 3.14) because coincurve currently ships wheels only up to cp313;
# on 3.14 pip falls back to a source build that fails.

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv

LABEL org.opencontainers.image.title="satoshi-scanner" \
      org.opencontainers.image.description="Educational Bitcoin address scanner with Telegram alerts and Prometheus metrics." \
      org.opencontainers.image.source="https://github.com/sephiman/satoshi-scanner" \
      org.opencontainers.image.licenses="AGPL-3.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    METRICS_PORT=8000

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

COPY bot/ ./bot/

# Run as an unprivileged user rather than root; /app/data holds the
# found-wallets record and is meant to be a volume.
RUN useradd --system --no-create-home --uid 10001 scanner \
    && mkdir -p /app/data \
    && chown scanner:scanner /app/data
USER scanner

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Liveness = the Prometheus endpoint answers. Respects METRICS_PORT.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('METRICS_PORT','8000')+'/metrics', timeout=4)" || exit 1

CMD ["python", "bot/main.py"]
