#!/usr/bin/env bash
# Resolve the interpreter that has the backend dependencies installed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -x "$ROOT/backend/.venv/Scripts/python.exe" ]; then
  printf '%s\n' "$ROOT/backend/.venv/Scripts/python.exe"
elif [ -x "$ROOT/backend/.venv/bin/python" ]; then
  printf '%s\n' "$ROOT/backend/.venv/bin/python"
else
  exit 1
fi
