# PayFlow Webhook Ingestion & Dispatch Runbook

- **Date**: 2026-08-20
- **Version**: 1.2 (Stale - Last updated Aug 20, 2026)

## Retry Policy
- **Maximum Retries**: 3 attempts with exponential backoff (1s, 2s, 4s).
*(Notice: The production codebase in PR #65 updated max_attempts to 5; this is stale).*

## Configuration
- `STRIPE_WEBHOOK_SECRET_OLD`: Stale legacy secret key referenced in fallback routines.
