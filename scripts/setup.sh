#!/usr/bin/env bash
# One-time local setup: backend venv, frontend dependencies, .env from the template.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Backend"
if [ -x "backend/.venv/Scripts/python.exe" ]; then
  PY="backend/.venv/Scripts/python.exe"
elif [ -x "backend/.venv/bin/python" ]; then
  PY="backend/.venv/bin/python"
else
  python -m venv backend/.venv
  if [ -x "backend/.venv/Scripts/python.exe" ]; then
    PY="backend/.venv/Scripts/python.exe"
  else
    PY="backend/.venv/bin/python"
  fi
fi

"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --editable "backend[dev]"

echo "==> Frontend"
npm --prefix frontend install --no-fund --no-audit

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "==> Created .env from .env.example"
fi

echo
echo "Setup complete. Start both servers with: npm run dev   (or: make dev)"
