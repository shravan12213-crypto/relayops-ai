# RelayOps Evaluation & Quality Metrics Report

> **Automated Quality Benchmark Report**  
> Generated: `2026-11-09T18:36:23.126383+00:00`  
> Evaluation Target: PayFlow Golden Path Dataset (`backend/seed/ground_truth.json`)  
> Environment: Replay / Zero-Key Deterministic Mode  

---

## Executive Summary

| Metric | Target | Result | Status |
|---|---|---|---|
| **Ground Truth Scenarios Detected** | 10 / 10 (100%) | **10 / 10 (100.0%)** | PASS |
| **Planted Secret Redaction Recall** | 100.0% | **100.0% (7/7 secrets)** | PASS |
| **Secret Leakage Rate** | 0.0% | **0 raw secret leaks** | PASS |
| **Hallucination Rate** | 0.0% | **0.0% (0 invalid claims)** | PASS |
| **Evidence Link Validity** | 100.0% | **100.0% (9/9 grounded)** | PASS |
| **Access Control / Firewall Leak Rate** | 0.0% | **0.0% (0 leaks)** | PASS |
| **Cryptographic Audit Chain Integrity** | VALID | **VALID (53 entries)** | PASS |

---

## 1. Ground Truth Scenario Verification (10 / 10)

Every scenario from `ground_truth.json` is validated by deterministic rules and authority weights:

| # | Scenario Description | Expected Kind | Result |
|---|---|---|---|
| 1 | Redis session caching proposed in ADR-003 abandoned for stateless JWT in PR #89 | `SUPERSEDES` | ✅ PASSED |
| 2 | MongoDB evaluation in RFC-007 superseded by PostgreSQL migration in PR #42 | `SUPERSEDES` | ✅ PASSED |
| 3 | Payment provider rate limit disagreement (100/min vs 500/min) | `CONFLICT` | ✅ PASSED |
| 4 | Webhook retry limit contradiction between runbook and code | `CONTRADICTION` | ✅ PASSED |
| 5 | Two unmerged branches with active development work | `AMBIGUITY` | ✅ PASSED |
| 6 | Open blocker PAY-142 with confidential escalation contact in private channel | `BLOCKER` | ✅ PASSED |
| 7 | Module ledger-sync has no documentation and single author (bus factor risk) | `AMBIGUITY` | ✅ PASSED |
| 8 | Planted fake secrets requiring automatic redaction at ingestion | `SECRET_REDACTION` | ✅ PASSED |
| 9 | Stale configuration variable reference STRIPE_WEBHOOK_SECRET_OLD | `AMBIGUITY` | ✅ PASSED |
| 10 | Unclosed Slack thread with unanswered handover question to Aarav | `AMBIGUITY` | ✅ PASSED |

---

## 2. Ingestion Secret Redaction Benchmark

RelayOps enforces zero-secret storage: all regex patterns and Shannon entropy token detectors run in-memory **before database storage** and before LLM prompting.

- **Total Planted Secrets Evaluated:** 7
  - API Keys (`sk_test_FAKE_...`): Redacted (`[REDACTED_API_KEY]`)
  - AWS Access Keys (`AKIAFAKE...`): Redacted (`[REDACTED_AWS_KEY]`)
  - Bearer JWT Tokens (`Bearer fake_jwt...`): Redacted (`[REDACTED_BEARER]`)
  - Database Connection URLs (`postgres://...`): Redacted (`[REDACTED_DB_URL]`)
  - Sensitive Emails (`david.vance@acquirercorp.com`): Redacted (`[REDACTED_EMAIL]`)
  - Phone Numbers (`+1-555-019-2834`): Redacted (`[REDACTED_PHONE]`)
  - Salary Figures (`$185,000`): Redacted (`[REDACTED_COMPENSATION]`)
- **Total Redaction Events Fired Across Dataset:** 78
- **Raw Secret Leakage:** 0 bytes (100% sanitized)

---

## 3. Epistemic Verification & Hallucination Prevention

In RelayOps, **every claim presented to a successor must bind to real project artifacts**:

- **Total Claims Extracted:** 9
- **Claims with Valid Bound Evidence:** 9
- **Unsupported / Fabricated Claims Persisted as Verified:** 0
- **Measured Hallucination Rate:** `0.00%`

---

## 4. Input-Filtered Access Control & Firewall Enforcement

Access control is evaluated strictly **before retrieval and context synthesis**:

- **Contractor Security Clearance:** Level 1 (Internal)
- **Clearance Level 2 & 3 Items Hidden:** 100% masked
- **Confidential Escalations Exposed to Contractor:** 0
- **Contractor Data Leakage Rate:** `0.00%`

---

## 5. Cryptographic Audit Chain & Tamper-Evidence

- **Ledger Entries Hashed:** 53
- **Hash Algorithm:** Rolling SHA-256 with canonical JSON payload serialization
- **Cryptographic Chain State:** VALID and UNBROKEN
- **Tamper Detection Capability:** Verified via CLI `python -m app.cli tamper` $\rightarrow$ sequence discrepancy immediately flagged.

---
*Report certified by RelayOps Evaluation Engine (`backend/app/eval.py`).*
