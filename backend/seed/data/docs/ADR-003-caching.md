# ADR-003: Redis Session Store Architecture

- **Date**: 2026-10-12
- **Status**: Proposed (Oct 12, 2026) -> Superseded by PR #89 (Nov 2, 2026)
- **Author**: Aarav Kulkarni (akulkarni@payflow.dev)

## Proposal
Deploy a managed Redis 7.2 cluster to cache authenticated user sessions with a 12-hour TTL.

## Consequences & Reversal
On November 2, 2026, PR #89 officially superseded this decision. The team adopted stateless
HMAC-SHA256 signed JWT tokens instead.
