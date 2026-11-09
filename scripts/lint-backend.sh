#!/usr/bin/env bash
# Backend lint gate: ruff (lint + import order) then black in check mode.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! PY="$(bash scripts/python-path.sh)"; then
  echo "Backend virtualenv not found. Run: bash scripts/setup.sh" >&2
  exit 1
fi

cd backend
"$PY" -m ruff check .
"$PY" -m black --check .
