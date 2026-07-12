FROM python:3.13-slim

# 3.13 (not 3.14) because coincurve currently ships wheels only up to cp313;
# on 3.14 pip falls back to a source build that fails.

LABEL org.opencontainers.image.title="satoshi-scanner" \
      org.opencontainers.image.description="Educational Bitcoin address scanner with Telegram alerts and Prometheus metrics." \
      org.opencontainers.image.source="https://github.com/sephiman/satoshi-scanner" \
      org.opencontainers.image.licenses="AGPL-3.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    METRICS_PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot/ ./bot/

# Run as an unprivileged user rather than root.
RUN useradd --system --no-create-home --uid 10001 scanner
USER scanner

EXPOSE 8000

# Liveness = the Prometheus endpoint answers. Respects METRICS_PORT.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('METRICS_PORT','8000')+'/metrics', timeout=4)" || exit 1

CMD ["python", "bot/main.py"]
