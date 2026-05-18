# ════════════════════════════════════════════════════════════════════════════
# JORINOVA NEXUS ALIS-X — Production Dockerfile
# ════════════════════════════════════════════════════════════════════════════
# Multi-stage: builder → runtime (smaller final image, no dev tools)
# ════════════════════════════════════════════════════════════════════════════

# ── Stage 1: Build dependencies ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a virtual environment
COPY requirements.txt requirements-prod.txt* ./
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip wheel && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt && \
    if [ -f requirements-prod.txt ]; then \
        /opt/venv/bin/pip install --no-cache-dir -r requirements-prod.txt; \
    fi


# ── Stage 2: Runtime image ───────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    ca-certificates \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy application source
COPY . .

# Create required directories
RUN mkdir -p /app/media/staff_photos \
             /app/media/vision \
             /app/logs \
             /app/data

# Create non-root user for security
RUN groupadd -r alisapp && \
    useradd -r -g alisapp -s /bin/false alisapp && \
    chown -R alisapp:alisapp /app

USER alisapp

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8000/api/v1/health || exit 1

# Default: production gunicorn
CMD ["gunicorn", "main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--access-logfile", "/app/logs/access.log", \
     "--error-logfile",  "/app/logs/error.log", \
     "--log-level", "warning", \
     "--forwarded-allow-ips=*"]
