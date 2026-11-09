#!/usr/bin/env bash
# Run the FastAPI backend (:8000) and the Vite dev server (:5173) together.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! PY="$(bash scripts/python-path.sh)"; then
  echo "Backend virtualenv not found. Run: bash scripts/setup.sh" >&2
  exit 1
fi

API_PID=""
WEB_PID=""

cleanup() {
  trap - INT TERM EXIT
  for pid in "$WEB_PID" "$API_PID"; do
    [ -n "$pid" ] || continue
    if command -v taskkill >/dev/null 2>&1; then
      taskkill //PID "$pid" //T //F >/dev/null 2>&1 || true
    else
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "==> API    http://127.0.0.1:8000  (docs: /api/docs)"
echo "==> Web    http://127.0.0.1:5173"
echo

(cd backend && "$PY" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
API_PID=$!

(cd frontend && npm run dev) &
WEB_PID=$!

wait -n "$API_PID" "$WEB_PID"
