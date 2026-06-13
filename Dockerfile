# ── UpSearch Dockerfile ───────────────────────────────────────────────────────
# Multi-stage build with no credentials baked into the image.
#
# Build:
#   docker build -t upsearch .
#
# Run (dev):
#   docker run -p 8000:8000 -v "$(pwd)/.upsearch:/app/.upsearch" \
#     -v "$(pwd)/opportunity_os.db:/app/opportunity_os.db" \
#     --env-file .env upsearch
#
# Run with docker compose:
#   docker compose up

# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY upsearch/ upsearch/
COPY agents/ agents/
COPY db.py server.py profile.txt ./

# Install build dependencies and create a minimal venv
RUN pip install --no-cache-dir uv && \
    uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

# Copy the pre-built venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY upsearch/ upsearch/
COPY agents/ agents/
COPY db.py server.py profile.txt pyproject.toml ./

# Runtime user (non-root)
RUN addgroup --system --gid 1001 upsearch && \
    adduser --system --uid 1001 --gid 1001 upsearch && \
    mkdir -p /app/.upsearch && \
    chown -R upsearch:upsearch /app
USER upsearch

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/os/health')" || exit 1

# Default command: API server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
