#!/usr/bin/env bash
# Smoke test script for RelayOps: verifies health, login, demo load, and pipeline.
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
COOKIE_JAR="$(mktemp -t relayops_smoke_cookies.XXXXXX 2>/dev/null || mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

echo "=================================================="
echo "RelayOps Production Smoke Test"
echo "Target URL: $BASE_URL"
echo "=================================================="

FAILED=0

# Step 1: Healthcheck
echo -n "[1/5] Checking health endpoint (/api/v1/health)... "
HEALTH_RESP=$(curl -s -f "$BASE_URL/api/v1/health" 2>/dev/null || echo "")
if [[ -n "$HEALTH_RESP" && "$HEALTH_RESP" == *"ok"* ]]; then
  echo "PASS"
else
  echo "FAIL: Health endpoint unreachable or not ok ($HEALTH_RESP)"
  FAILED=1
fi

# Step 2: Authentication
echo -n "[2/5] Authenticating as Aarav Kulkarni (Outgoing Lead)... "
LOGIN_RESP=$(curl -s -c "$COOKIE_JAR" -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"aarav@payflow.dev","password":"password123"}' 2>/dev/null || echo "")

if [[ -n "$LOGIN_RESP" && "$LOGIN_RESP" == *"aarav@payflow.dev"* ]]; then
  echo "PASS"
else
  echo "FAIL: Login failed ($LOGIN_RESP)"
  FAILED=1
fi

# Step 3: Demo Dataset Load
echo -n "[3/5] Verifying / loading PayFlow demo dataset... "
DEMO_RESP=$(curl -s -b "$COOKIE_JAR" -X POST "$BASE_URL/api/v1/projects/payflow/demo-load" 2>/dev/null || echo "")
if [[ -n "$DEMO_RESP" && ("$DEMO_RESP" == *"payflow"* || "$DEMO_RESP" == *"artifacts_created"* || "$DEMO_RESP" == *"already"* || "$DEMO_RESP" == *"PayFlow"*) ]]; then
  echo "PASS"
else
  echo "FAIL: Demo load failed ($DEMO_RESP)"
  FAILED=1
fi

# Step 4: Handover Discovery & Pipeline Execution
echo -n "[4/5] Running reconstruction & verification pipeline... "
HANDOVERS_RESP=$(curl -s -b "$COOKIE_JAR" "$BASE_URL/api/v1/handovers?project_slug=payflow" 2>/dev/null || echo "")
HANDOVER_ID=$(echo "$HANDOVERS_RESP" | grep -o '"id":"[A-Za-z0-9_]*"' | head -n 1 | cut -d'"' -f4 || echo "")

if [[ -z "$HANDOVER_ID" ]]; then
  CREATE_RESP=$(curl -s -b "$COOKIE_JAR" -X POST "$BASE_URL/api/v1/handovers" \
    -H "Content-Type: application/json" \
    -d '{"project_slug":"payflow","notes":"Smoke Test Handover"}' 2>/dev/null || echo "")
  HANDOVER_ID=$(echo "$CREATE_RESP" | grep -o '"id":"[A-Za-z0-9_]*"' | head -n 1 | cut -d'"' -f4 || echo "")
fi

if [[ -n "$HANDOVER_ID" ]]; then
  RUN_RESP=$(curl -s -b "$COOKIE_JAR" -X POST "$BASE_URL/api/v1/handovers/$HANDOVER_ID/run" 2>/dev/null || echo "")
  if [[ -n "$RUN_RESP" && "$RUN_RESP" == *"job_id"* ]]; then
    echo "PASS (Handover: $HANDOVER_ID)"
  else
    echo "FAIL: Pipeline trigger failed ($RUN_RESP)"
    FAILED=1
  fi
else
  echo "FAIL: Could not discover or create handover ($HANDOVERS_RESP)"
  FAILED=1
fi

# Step 5: Grounded Claims & Citations
echo -n "[5/5] Verifying grounded claims & epistemic evidence... "
CLAIMS_RESP=$(curl -s -b "$COOKIE_JAR" "$BASE_URL/api/v1/handovers/$HANDOVER_ID/claims" 2>/dev/null || echo "")
if [[ -n "$CLAIMS_RESP" && ("$CLAIMS_RESP" == *"evidence"* || "$CLAIMS_RESP" == *"items"*) ]]; then
  echo "PASS"
else
  echo "FAIL: No verified claims returned ($CLAIMS_RESP)"
  FAILED=1
fi

echo "=================================================="
if [[ $FAILED -eq 0 ]]; then
  echo "ALL SMOKE CHECKS PASSED: Application is healthy and production-ready."
  exit 0
else
  echo "SMOKE TEST FAILED: Please inspect server logs."
  exit 1
fi
