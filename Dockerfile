# SpyChat — production image
FROM python:3.12-slim

# Pillow needs a couple of runtime libs for common image formats.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SPYCHAT_DATA_DIR=/data
# Set SPYCHAT_SECRET_KEY (and SPYCHAT_SECURE_COOKIES=1 behind HTTPS) at runtime.

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml requirements.txt README.md ./
COPY spychat ./spychat
RUN pip install --no-cache-dir ".[prod]"

# Persisted profile lives on a volume.
RUN mkdir -p /data
VOLUME ["/data"]

# Run as a non-root user.
RUN useradd --create-home --uid 10001 spy && chown -R spy:spy /data
USER spy

EXPOSE 8000

# 2 workers is plenty for this lightweight app; tune with GUNICORN_CMD_ARGS.
CMD ["gunicorn", "spychat.wsgi:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
