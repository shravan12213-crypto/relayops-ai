# RelayOps: Project Context (read fully before every task)

## What we are building
RelayOps converts scattered project activity (git commits, PRs, issue tickets, chat exports, ADR/markdown docs)
into a TRACEABLE, HUMAN-VERIFIED handover when a team member leaves. It is not a chatbot.
Pipeline (5 stages): CONNECT -> RECONSTRUCT -> VERIFY -> REVIEW -> HANDOVER.

## Non-negotiable product rules
1. Every claim shown to a successor has >=1 evidence link to a real artifact (source_uri + snippet). Claims with
   zero valid evidence are REJECTED by the validator and never persisted as "verified".
2. When evidence is missing or conflicting, we say so (Ambiguity Ledger). We never smooth over gaps.
3. Secrets/PII are scrubbed at ingestion, BEFORE storage of the searchable text and BEFORE any LLM call.
4. Access control is applied BEFORE retrieval/LLM calls (filter inputs), not by hiding output afterwards.
5. A handover cannot be delivered until BOTH the outgoing contributor and the lead sign off.
6. The app must work with NO LLM key (replay/mock mode on seeded data) and with a key (live mode).

## Tech stack (do not add dependencies without a written reason in the PR/commit message)
Backend: Python 3.11+, FastAPI, SQLModel, SQLite (WAL, FTS5), httpx, pydantic v2, pytest.
LLM: single module backend/app/llm.py (Anthropic or OpenAI SDK by env), JSON-schema outputs, replay cache.
Frontend: Vite + React 18 + TypeScript (strict), Tailwind, shadcn/ui, TanStack Query, React Router, React Flow,
lucide-react, sonner. No Redux, no Next.js, no GraphQL, no ORM other than SQLModel.
Deploy: one Docker image; FastAPI serves /api/* and the built SPA at /.

## Repo layout
The repository root (this folder) is the `relayops/` root in the build plan:

```
backend/app/{main.py,config.py,db.py,models.py,schemas.py,auth.py,policy.py,llm.py,jobs.py}
backend/app/ingest/{base.py,github.py,json_loaders.py,markdown.py,normalize.py,redact.py}
backend/app/reconstruct/{entities.py,graph.py,authority.py,extract.py}
backend/app/verify/{citations.py,conflicts.py,ambiguity.py,scorecard.py}
backend/app/handover/{claims.py,versions.py,signoff.py,views.py,plan.py,copilot.py,export.py}
backend/app/routers/*.py
backend/tests/
backend/seed/{generate_dataset.py,data/*.json,data/docs/*.md,ground_truth.json}
frontend/src/{app,components,pages,lib,hooks,styles}
e2e/ ; docs/ ; Dockerfile ; docker-compose.yml ; .env.example ; README.md
```

## Conventions
- API: REST JSON under /api/v1. Errors: `{"error":{"code":"STRING","message":"human text","details":{}}}` with proper HTTP codes.
- IDs: ULID strings. Timestamps: UTC ISO-8601 in DB/API; the UI renders in the user's local timezone.
- Evidence reference format everywhere: `{"artifact_id","source_uri","snippet","char_start","char_end"}`.
- Source authority weights: merged_code/PR=1.0, issue_ticket=0.8, adr_or_meeting_doc=0.6, chat=0.4.
- Sensitivity levels: 0 public, 1 internal, 2 confidential, 3 restricted. Users have clearance 0-3.
  Roles: lead, outgoing, successor, contractor, auditor.
- Claim kinds: architecture_decision, ownership, blocker, runbook, risk, dependency, open_work, contact, credential_ref.
- Claim status: draft | accepted | edited | rejected | needs_review.
- Python: type hints everywhere, ruff + black formatting, no bare except, log with `logging`, no print.
- TS: strict mode, no `any`, components < 200 lines, data fetching only via TanStack Query hooks in src/lib/api.
- Every endpoint has a pytest. Every pure function in redact/authority/conflicts/policy has unit tests.
- Never commit secrets. Seed data secrets are FAKE and clearly marked (e.g. sk_test_FAKE_...).
- Commit small, message format: `feat(ingest): ...`, `fix(ui): ...`, `test(policy): ...`.
- After finishing a task: run backend tests + `npm run typecheck && npm run build`, and report what passed.

## UI principles (applies to ALL frontend work)
Calm, dense-but-readable, "developer tool meets editorial". Neutral slate palette, one accent (indigo),
semantic colors only for status (green verified, amber needs review, red conflict, slate unverified).
Inter (UI) + JetBrains Mono (ids/code). 8px spacing grid. Rounded-lg, subtle borders, soft shadows.
Every list/page has: loading skeleton, empty state with CTA, error state with retry. Transitions 150-200ms,
respect prefers-reduced-motion. Keyboard accessible (focus rings, Esc closes drawers, j/k to move in review).
Dark mode via class strategy, persisted. Responsive down to 1024px fully, 768px gracefully.

---

# Local environment notes (machine-specific, keep this section truthful)

- OS: Windows 11, shell is Git Bash. The repo lives at `C:\Users\shravan\Documents\GitHub\relayops-ai`.
- Python: only CPython **3.14** is installed (`C:\Python314`), no 3.11. Code must stay 3.11+ compatible;
  CI pins 3.11, local dev runs 3.14. Backend venv: `backend/.venv`.
- Node 24 / npm 11. Frontend is an npm project under `frontend/`.
- **`make` is not installed on this machine.** The Makefile targets (`make dev|test|build|seed`) are the
  documented interface and delegate to `scripts/*.sh`; locally use `bash scripts/dev.sh` or `npm run dev`.
  Never make a task depend on `make` existing.
- `npm run dev` is the canonical cross-platform way to run both servers; it shells out to `scripts/dev.sh`.
- Kanban of execution: prompts P01..P24 from `RelayOps_Build_Plan.md` are executed one at a time, in order,
  each ending only when its Acceptance checks pass.

# Implementation decisions that later prompts must not undo

- **React is pinned to 18.3** (plan requirement). shadcn/ui primitives are vendored under `frontend/src/components/ui`;
  the generated `sonner.tsx` depends on `next-themes`, which was removed — theme state lives in
  `src/app/theme-context.ts` + `theme-provider.tsx`. Do not re-add `next-themes`.
- Tailwind is **v3** with `darkMode: ["class"]` and HSL CSS variables in `src/styles/globals.css`; status colours
  (`verified`, `needs-review`, `conflict`, `unverified`) are first-class theme tokens.
- Vite is bound to `127.0.0.1:5173` (strict port) and proxies `/api` to `127.0.0.1:8000`. Print/use `127.0.0.1`,
  not `localhost`: on this machine `localhost` resolves to IPv6 and a 127.0.0.1-bound server misses it.
- The SPA mount answers unknown client routes with `index.html`, but never for `/api/*` or `/assets/*` —
  those must keep returning the standard JSON 404 envelope (regression test: `tests/test_spa_hosting.py`).
- SQLite URLs are anchored to `backend/` (`app.db.resolve_database_url`), so the DB is the same file no matter
  which directory starts uvicorn. `backend/data/` is gitignored.
