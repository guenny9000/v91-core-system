# syntax=docker/dockerfile:1
# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install deps into a prefix so we can copy only what we need
COPY requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Security: run as non-root
RUN addgroup --system v91 && adduser --system --ingroup v91 v91

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy source (controller only – no tests, no secrets)
COPY controller/ ./controller/

# Use non-root user
USER v91

# Health-check endpoint used by docker-compose
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import sqlite3,os,sys; p=os.environ.get('V91_DB_PATH','/app/data/v91_independent_state.db'); sqlite3.connect(p).execute('SELECT 1 FROM v91_ledger LIMIT 1'); print('ok')"

CMD ["python", "controller/v91_listener.py"]
