FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# App code + Python deps
COPY . .
RUN pip install --no-cache-dir .

# Health check — PORT je nastavený Railway, fallback na AGENT_API_PORT alebo 8001
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-${AGENT_API_PORT:-8001}}/health || exit 1

CMD ["python", "main.py"]
