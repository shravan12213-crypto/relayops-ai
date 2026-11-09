#!/usr/bin/env bash
# Build the SPA into frontend/dist, which FastAPI serves at /.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"

npm run build

echo
echo "Built frontend/dist — start the API and open http://127.0.0.1:8000"
