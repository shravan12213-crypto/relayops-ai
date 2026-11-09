# RelayOps Production Deployment Guide

This guide documents deploying RelayOps as a single self-hosted container using Docker, Docker Compose, Render, or Fly.io with persistent SQLite storage and zero-key replay operation.

---

## Architecture Overview

RelayOps is built as a single container serving both the React Single Page Application (SPA) and the FastAPI backend:
- **Port:** `8000` (FastAPI serves `/api/v1/*` and the static SPA at `/` with client-side push-state routing)
- **Database:** SQLite with WAL mode and FTS5 full-text search stored on a persistent disk mount
- **Zero-Key Replay Mode:** Bundled `backend/seed/llm_recordings.json` allows full evaluation and usage without any OpenAI or Anthropic API key.

---

## 1. Local & On-Premise: Docker & Docker Compose

### Prerequisites
- Docker Engine 24+ and Docker Compose v2+

### Quickstart
```bash
# Clone repository
git clone https://github.com/payflow/relayops.git
cd relayops

# Build and start container in background
docker compose up --build -d
```

Open your browser at `http://localhost:8000`. You will be greeted by the RelayOps login screen with one-click demo personas ready to explore.

### Managing the Container
```bash
# View container logs
docker compose logs -f relayops

# Inspect healthcheck status
docker inspect --format='{{json .State.Health}}' relayops-app

# Stop container
docker compose down
```

---

## 2. Cloud Deployment: Render (One-Click Blueprint)

Render provides a managed container platform with persistent disk support.

### One-Click Deployment Steps

1. **Fork or Push** your repository to GitHub or GitLab.
2. Log in to [Render Dashboard](https://dashboard.render.com).
3. Click **New +** $\rightarrow$ **Blueprint**.
4. Connect your `relayops` repository. Render will automatically detect [`render.yaml`](../render.yaml).
5. Click **Apply**:
   - Render automatically provisions the Docker web service.
   - Attaches a **1 GB persistent disk** mounted at `/app/data` for SQLite.
   - Generates a cryptographically strong 32+ character `SECRET_KEY`.
   - Runs healthchecks against `/api/v1/health`.
6. Once deployed, open your service's `onrender.com` URL.

---

## 3. Cloud Deployment: Fly.io

Fly.io runs containers close to users with local NVMe volumes.

### Step-by-Step Deployment

1. Install Fly CLI:
   ```bash
   # macOS / Linux
   curl -L https://fly.io/install.sh | sh
   # Windows (PowerShell)
   iwr https://fly.io/install.ps1 -useb | iex
   ```

2. Log in and launch:
   ```bash
   fly auth login
   ```

3. Create persistent storage volume:
   ```bash
   fly volumes create relayops_data --region iad --size 1
   ```

4. Set production secret key (must be $\ge 32$ characters):
   ```bash
   fly secrets set SECRET_KEY=$(openssl rand -hex 32)
   ```

5. Deploy:
   ```bash
   fly deploy
   ```

6. Open application:
   ```bash
   fly open
   ```

---

## 4. Production Security & Fail-Fast Guarantees

When running with `ENV=prod` or `ENV=production`:
- **Strict Secret Key Requirement:** If `SECRET_KEY` is left as the default development string or is shorter than 32 characters, the backend **aborts startup immediately** with a clear error:
  ```text
  FATAL: Unsafe production configuration detected!
  When ENV=prod or ENV=production, SECRET_KEY cannot use the default value and must be at least 32 characters long.
  ```
- **Security Headers:** The server automatically applies:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Content-Security-Policy` restricting script and style execution
- **Non-Root Execution:** The container runs under an unprivileged `relayops` system user (UID 1000).

---

## 5. Safe Database Backups

RelayOps uses SQLite's official online backup API, streaming database pages safely even under concurrent write load without locking the database:

```bash
# Inside running container or host environment:
docker compose exec relayops python -m app.cli backup --dest /app/data/backups/relayops_manual.db
```

Or on host:
```bash
python -m app.cli backup
```
Outputs:
```text
Creating safe online backup from '/app/data/relayops.db' to '/app/data/backup_relayops_20261110_001441.db'...
[OK] Backup completed successfully: /app/data/backup_relayops_20261110_001441.db (1171456 bytes)
```

---

## 6. End-to-End Smoke Verification

To verify that a deployed instance is operational, run the automated smoke test:

```bash
bash scripts/smoke.sh http://localhost:8000
```
This script exercises:
- Service health check
- User authentication
- Demo data ingestion
- Pipeline execution
- Successor role-scoped view verification
- Access control firewall validation
