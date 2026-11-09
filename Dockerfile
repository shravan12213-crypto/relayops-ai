# ==============================================================================
# Stage 1: Frontend SPA Build
# ==============================================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /build

# Copy npm package definitions and install with deterministic lockfile
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy frontend source code and compile production assets
COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Python Backend Runtime
# ==============================================================================
FROM python:3.11-slim AS runtime

# Install system utilities: curl (healthcheck) & sqlite3 (online safe backup)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user and directory structure
RUN useradd -m -u 1000 -s /bin/bash relayops \
    && mkdir -p /app/data /app/backend/data /app/frontend/dist \
    && chown -R relayops:relayops /app

WORKDIR /app

# Copy full backend application code and seed datasets
COPY backend/ /app/backend/

# Install Python backend dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "/app/backend"

# Copy compiled SPA from frontend-builder stage into /app/frontend/dist
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Set permissions for unprivileged user
RUN chown -R relayops:relayops /app

# Switch to non-root user
USER relayops

# Default Environment Variables
ENV ENV=prod \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    DATABASE_URL=sqlite:////app/data/relayops.db \
    SECRET_KEY=relayops-production-secret-change-me-32chars-min \
    LLM_PROVIDER=replay \
    SEED_ON_START=true \
    PORT=8000

# Expose HTTP port
EXPOSE 8000

# Persistent volume for SQLite database and storage
VOLUME ["/app/data"]

# Healthcheck on standard API endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/api/v1/health || exit 1

# Launch uvicorn production server
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
