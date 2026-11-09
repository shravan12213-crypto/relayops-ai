# RelayOps: End-to-End Build Plan (Prompt Segments for Coding Agents)

How to use this file:
1. Read **Part A** (decisions) once.
2. Paste **Part B** (Master Context) into the agent as `CLAUDE.md` / `AGENTS.md` at the repo root. Every later prompt assumes it.
3. Run prompts **P01 → P24 in order**, one per agent session. Each prompt ends with *Acceptance* checks. Do not move on until they pass.
4. Part D is the "small things" checklist. Part E is the demo script.

---

## PART A: Stack decisions (minimal, use-case driven)

Your dossier lists a heavy stack (Postgres + pgvector + Apache AGE, Celery + Redis, LangGraph, LlamaIndex, DeBERTa, Presidio, TruffleHog, Casbin, Next.js SSR). For a build that must **actually work and demo reliably**, most of that is risk without payoff. Every dossier feature is preserved, but implemented with fewer moving parts:

| Dossier claim | Minimal implementation | Why it's enough |
|---|---|---|
| Postgres + pgvector + AGE | **SQLite (WAL) + FTS5**; graph = `nodes` + `edges` tables, traversal via recursive CTEs | Zero setup, one file, ACID. Corpus is hundreds/thousands of artifacts. BM25 retrieval is *better* than embeddings for exact IDs, SHAs, ticket keys |
| Celery + Redis | FastAPI `BackgroundTasks` + a `jobs` table + SSE progress | One process; no broker to crash |
| LangGraph / LlamaIndex / LiteLLM | One small `llm.py` wrapper (Anthropic SDK or OpenAI SDK, chosen by env) with JSON-schema output + Pydantic validation + record/replay cache | Pipeline is a fixed 5-step DAG, not an open-ended agent |
| DeBERTa NLI | Deterministic rules first (authority weights + time ordering), LLM judge only for ambiguous pairs | No GPU/torch, no 1GB image |
| Presidio + TruffleHog | Own `redact.py`: regex patterns + Shannon-entropy token detector + email/phone/name rules | Small, testable, explainable to judges |
| Casbin ABAC | ~60-line `policy.py`: `can_view(user, resource)` using clearance level + role + project membership | One function, fully unit-testable |
| "Cryptographic sign-off" | SHA-256 **hash chain** over version snapshots + HMAC-signed sign-off records | Real tamper evidence, no PKI |
| Next.js 14 SSR | **Vite + React + TypeScript SPA**, served as static files by FastAPI | One container, one URL, no SSR needed (it's an authenticated app) |
| React Flow | Keep (only for timeline/dependency graph) | Genuinely needed |

**Final stack**
- Backend: Python 3.11, FastAPI, SQLModel (SQLAlchemy + Pydantic), SQLite + FTS5, httpx, pytest
- LLM: Anthropic or OpenAI SDK behind `llm.py` (env-configurable model), with a **replay cache** so the demo works offline
- Frontend: Vite, React 18, TypeScript, Tailwind CSS, shadcn/ui (Radix), TanStack Query, React Router, React Flow, Lucide icons, Sonner (toasts)
- Tests: pytest, Vitest (light), Playwright (one golden-path e2e)
- Deploy: single Dockerfile (multi-stage: build frontend → copy into Python image), Docker Compose with one service + volume; Render/Fly/Railway ready

---

## PART B: MASTER CONTEXT (paste into `CLAUDE.md` / `AGENTS.md`)

```
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
Backend: Python 3.11, FastAPI, SQLModel, SQLite (WAL, FTS5), httpx, pydantic v2, pytest.
LLM: single module backend/app/llm.py (Anthropic or OpenAI SDK by env), JSON-schema outputs, replay cache.
Frontend: Vite + React 18 + TypeScript (strict), Tailwind, shadcn/ui, TanStack Query, React Router, React Flow,
lucide-react, sonner. No Redux, no Next.js, no GraphQL, no ORM other than SQLModel.
Deploy: one Docker image; FastAPI serves /api/* and the built SPA at /.

## Repo layout
relayops/
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

## Conventions
- API: REST JSON under /api/v1. Errors: {"error":{"code":"STRING","message":"human text","details":{}}} with proper HTTP codes.
- IDs: ULID strings. Timestamps: UTC ISO-8601 in DB/API; the UI renders in the user's local timezone.
- Evidence reference format everywhere: {"artifact_id","source_uri","snippet","char_start","char_end"}.
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
```

---

## PART C: THE PROMPTS

### P01: Repo scaffold, tooling, config

```
Read CLAUDE.md. Create the monorepo skeleton exactly as in "Repo layout".

Backend:
- backend/pyproject.toml (fastapi, uvicorn[standard], sqlmodel, pydantic-settings, httpx, python-multipart,
  pyjwt, anthropic, openai, pytest, pytest-asyncio, ruff, black). Pin major versions.
- app/config.py using pydantic-settings: DATABASE_URL (default sqlite:///./data/relayops.db), SECRET_KEY,
  LLM_PROVIDER (anthropic|openai|replay), LLM_MODEL, ANTHROPIC_API_KEY, OPENAI_API_KEY, GITHUB_TOKEN (optional),
  CORS_ORIGINS, ENV (dev|prod), MAX_UPLOAD_MB=20, SEED_ON_START=true.
- app/main.py: FastAPI app, lifespan that creates DB + FTS tables + (optionally) seeds, CORS, request-id
  middleware, structured logging, global exception handler producing the standard error JSON,
  GET /api/v1/health returning {status, version, llm_mode, db: ok}. Mount built SPA from frontend/dist
  at "/" with SPA fallback to index.html (only if the dir exists).
Frontend:
- Vite + React + TS strict, Tailwind, shadcn/ui initialised (button, card, input, dialog, sheet, tabs, badge,
  tooltip, dropdown-menu, skeleton, toast via sonner, scroll-area, separator, select, textarea, checkbox),
  React Router, TanStack Query, lucide-react, React Flow. Vite dev proxy /api -> localhost:8000.
- Fonts: Inter + JetBrains Mono (self-hosted via @fontsource). Tailwind theme tokens for the palette in CLAUDE.md,
  CSS variables for light/dark.
Tooling: Makefile (make dev, make test, make build, make seed), .env.example, .gitignore, .editorconfig,
ruff/black config, ESLint + Prettier, GitHub Actions workflow (backend tests + frontend typecheck/build).

Acceptance: `make dev` starts both servers; /api/v1/health returns ok; the frontend shows a placeholder page
using the real theme; `make test` runs (even if 1 trivial test); CI file is valid.
```

### P02: Database models, migrations-lite, FTS

```
Read CLAUDE.md. Implement backend/app/models.py (SQLModel) and db.py. Use SQLite with WAL, foreign_keys=ON,
busy_timeout. Create tables on startup (no Alembic; add a `schema_version` table and a tiny migration runner
that applies numbered SQL files in backend/app/migrations/ so we can evolve schema safely).

Tables (all have id ULID PK, created_at, updated_at):
- user(email unique, name, password_hash, role, clearance int 0-3, is_active)
- project(name, slug unique, description, repo_url, status)
- project_member(project_id, user_id, project_role)
- source(project_id, type[github|jira_json|slack_json|markdown|pdf_text], name, config json, status, last_synced_at, stats json)
- artifact(project_id, source_id, kind[commit|pull_request|issue|chat_thread|adr_doc|meeting_note|code_file|branch],
  external_id, source_uri, title, body_redacted, body_hash, author_alias, author_entity_id nullable,
  valid_time (when it happened), transaction_time (when ingested), sensitivity int, acl_tags json,
  authority real, meta json, redaction_count int). UNIQUE(project_id, kind, external_id) for idempotent ingestion.
- redaction_event(artifact_id, rule, count, sample_masked)   # audit of what was scrubbed, never stores originals
- entity(project_id, type[person|module|service|external_api], canonical_name, aliases json, meta json)
- node(project_id, type[decision|blocker|module|person|commit|pr|issue|thread|doc|risk|runbook],
  key, label, props json, valid_from, valid_to nullable, tx_from, tx_to nullable, authority, artifact_id nullable)
- edge(project_id, src_node_id, dst_node_id, type[SUPERSEDES|BLOCKS|OWNS|CONTRADICTS|DEPENDS_ON|REFERENCES|AUTHORED],
  valid_from, valid_to nullable, confidence real, evidence json)
- handover(project_id, outgoing_user_id, successor_user_id, lead_user_id, status[draft|reconstructing|in_review|
  signed|delivered], current_version int, due_date, notes)
- claim(handover_id, section, kind, text, status, confidence real, sensitivity int, evidence json,
  origin[llm|rule|human], edited_by, rejected_reason, order_index, parent_claim_id nullable)
- ambiguity(handover_id, type[missing_doc|conflict|orphan_branch|unclosed_thread|stale_config|low_evidence|
  undocumented_module], severity[low|med|high], title, description, artifact_ids json, status[open|resolved|waived],
  resolution_note, resolved_by)
- handover_version(handover_id, version, snapshot json, prev_hash, hash, created_by, reason)
- signoff(handover_id, version, user_id, role, signature (HMAC), signed_at, comment)
- plan_item(handover_id, day_bucket[d1_7|d8_14|d15_30], title, description, priority, claim_ids json, status[todo|doing|done], assignee)
- receipt(handover_id, user_id, section, acknowledged_at, comprehension_note)
- chat_session(handover_id, user_id) ; chat_message(session_id, role, content, citations json, refused bool)
- job(project_id, handover_id nullable, kind, status[queued|running|done|failed], progress int, stage, log json, error)
- audit_log(seq autoincrement, actor_id, action, target_type, target_id, payload json, prev_hash, hash)

FTS5: virtual table artifact_fts(title, body_redacted, content='artifact') with triggers keeping it in sync,
plus a function search_artifacts(project_id, query, max_sensitivity, limit) that ALWAYS filters by sensitivity
in SQL (this is how the "pre-inference permission firewall" is enforced).

Also: db.py session dependency, helper `utcnow()`, ULID generator, and `audit(actor, action, ...)` that appends
to the hash-chained audit_log (hash = sha256(prev_hash + canonical json)). Provide `verify_audit_chain()`.

Tests: schema creation, UNIQUE idempotency, FTS sync + sensitivity filter, audit chain tamper detection.
Acceptance: pytest green; `verify_audit_chain()` returns False after manually editing a row in a test.
```

### P03: Auth + ABAC policy

```
Read CLAUDE.md. Implement auth.py, policy.py, routers/auth.py, routers/users.py.

Auth: email+password login -> JWT (HS256, 12h) in an httpOnly SameSite=Lax cookie AND returned for API use.
Password hashing with hashlib.scrypt (stdlib, no extra dep). Endpoints: POST /auth/login, POST /auth/logout,
GET /auth/me. Dependency `current_user`. Seed demo users (see P04) with a visible "Demo accounts" card on the login page.
Basic rate limit on login (in-memory, 10/min/IP). Return generic error on bad credentials.

policy.py (pure functions, no DB calls inside so they are easily unit tested):
- can_view_artifact(user, artifact) : user.clearance >= artifact.sensitivity AND user is project member
- can_view_claim(user, claim)       : user.clearance >= claim.sensitivity
- effective_clearance(user, handover): contractor capped at 1, auditor capped at 1 and may see claim metadata only
  (no raw artifact bodies), successor = their clearance, lead/outgoing = their clearance
- mask_claim(claim, user): returns the claim with text replaced by "Restricted: requires clearance N" and evidence
  stripped when not viewable. Used by views.
- allowed_actions(user, handover): who may edit claims, sign off (only outgoing + lead), view audit log (lead, auditor), etc.
Document the policy table in docs/POLICY.md.

Tests: exhaustive table-driven tests over role x clearance x sensitivity. Acceptance: pytest green; /auth/me works with cookie.
```

### P04: Synthetic dataset + ground truth (critical for demo and tests)

```
Read CLAUDE.md. Build backend/seed/generate_dataset.py that writes deterministic (fixed seed) files into
backend/seed/data/ and a ground_truth.json. The story: project "PayFlow", team of 5 (Aarav [OUTGOING lead backend],
Meera [lead/manager], Kabir [SUCCESSOR, junior], Sana, Dev [contractor]). Aarav is leaving mid-way through a payment
webhook refactor. Timeline Aug-Nov 2026.

Generate (realistic, messy, human-sounding; 150-300 artifacts total):
- commits.json (~80 commits with sha, author, date, message, files, a few with merged PR refs),
  pull_requests.json (~25 PRs incl. 2 open, 1 closed-unmerged, review comments),
  branches.json (including 2 UNMERGED branches with real work: `feature/webhook-retry-v2`, `hotfix/idempotency-keys`),
  issues.json (Jira-style keys PAY-101..., states, blockers, links),
  slack_backend-dev.json, slack_leads-private.json (sensitivity=confidential: HR/perf/salary-ish chatter and
  a vendor negotiation), slack_incidents.json, with threaded replies and aliases (same person appears as
  "aarav.k", "Aarav Kulkarni", "akulkarni@payflow.dev", GitHub "aarav-dev").
- docs/*.md: ADR-003 caching (proposes Redis sessions), RFC-007 DB choice (proposes MongoDB), runbook-webhooks.md
  (stale), onboarding.md, a meeting note.
PLANTED GROUND-TRUTH SCENARIOS (list each in ground_truth.json with expected artifact ids):
 1. Redis session caching proposed (ADR-003, Oct 12) -> abandoned for stateless JWT in PR #89 (Nov 2)  => SUPERSEDES
 2. MongoDB debated in March-style chat -> PostgreSQL migration merged in PR  => SUPERSEDES
 3. Two contemporaneous chat messages disagree on the payment provider rate limit (100/min vs 500/min) with no code
    resolution => UNRESOLVED CONFLICT
 4. Runbook claims retry limit 3, code says 5 => doc-vs-code CONTRADICTION (code wins by authority)
 5. Two unmerged branches => orphan_branch ambiguities
 6. An open blocker PAY-142 (vendor sandbox access) with an escalation contact in a private thread (confidential)
 7. A module `ledger-sync` with no docs and only Aarav as author => undocumented_module + bus-factor risk
 8. Planted FAKE secrets: sk_test_FAKE_..., AWS-style AKIA FAKE key, a bearer token, DB URL with password, emails, phone
    numbers, a salary figure in the private channel => must be redacted (ground truth lists them)
 9. A stale env var STRIPE_WEBHOOK_SECRET_OLD still referenced in config => stale_config
 10. An unclosed Slack thread where a question to Aarav got no answer => unclosed_thread
Also write users.json (5 users + the 5 roles/clearances) and the GitHub-style "expected output" checklist
ground_truth.json: expected claims (kind + key phrase), expected conflicts, expected ambiguities, expected redactions.

Make the generator reproducible: `python -m seed.generate_dataset` regenerates identical files.
Acceptance: files exist, JSON validates against small pydantic schemas in backend/seed/schemas.py, ground_truth.json
references only artifacts that exist, and a test confirms all 10 scenarios are present.
```

### P05: Ingestion gateway (CONNECT)

```
Read CLAUDE.md. Implement backend/app/ingest/*.

- base.py: `Loader` protocol -> yields `RawEvent` (kind, external_id, source_uri, title, body, author_alias,
  occurred_at, meta, acl_hint). Loaders must be pure (no DB writes).
- json_loaders.py: loaders for the seed formats (commits, PRs, branches, issues, slack threads). Thread = one artifact
  with replies concatenated and per-message offsets in meta so evidence snippets can point to a message.
- markdown.py: loader for .md/.txt (and PDF text via `pypdf` ONLY if already added in P01, otherwise plain text);
  infer kind (adr_doc / meeting_note / runbook) from filename/frontmatter.
- github.py: optional live loader using REST with GITHUB_TOKEN via httpx: commits, PRs (+review comments), issues,
  branches ahead of default. Respect rate limits (read X-RateLimit headers, back off), pagination, a max_items cap,
  and ETag caching. Must degrade gracefully (clear error message) with no token / private repo.
- normalize.py: RawEvent -> artifact rows: compute body_hash, set authority by kind (merged PR/commit 1.0, issue 0.8,
  adr/meeting 0.6, chat 0.4; unmerged/closed-unmerged PR = 0.5), sensitivity from acl_hint (private channel => 2,
  repos flagged restricted => 3, default 1), valid_time from occurred_at, transaction_time=now.
  Idempotent upsert by (project_id, kind, external_id); changed body_hash => update + keep old in meta.history.
- Sources API (routers/sources.py): POST /projects/{id}/sources (type + config or file upload with size/type limits),
  POST /sources/{id}/sync (starts a job), GET /sources, DELETE (soft). A one-click "Load PayFlow demo dataset" endpoint.
- Every sync goes through redact.py (P06) before body_redacted is stored. Wire the hook now with a stub that P06 fills.
- Sync is a background job writing progress/log lines to the job table.

Tests: loaders on seed data produce expected counts; re-sync is idempotent; upload rejects oversize/wrong types.
Acceptance: calling the demo-load endpoint creates ~all artifacts; counts per kind match ground_truth.
```

### P06: Redaction engine

```
Read CLAUDE.md. Implement backend/app/ingest/redact.py as a standalone, dependency-free module.

`redact(text, *, level) -> RedactionResult(text, events[list of {rule, count, span_count, sample_masked}])`.
Rules (each a named, unit-tested function, ordered): AWS access keys/secrets, generic `sk_(live|test)_...`, GitHub tokens
(ghp_/github_pat_), Slack tokens (xox*), JWTs, `Bearer <token>`, private key blocks, DB/connection URLs with creds
(mask only the password), `KEY=VALUE` env lines where key name matches SECRET|TOKEN|PASSWORD|KEY, high-entropy strings
(Shannon entropy > 4.0 and length >= 20, excluding git SHAs/UUIDs/known-safe patterns), emails, phone numbers,
salary/compensation patterns (currency + "salary|CTC|comp|raise|bonus"), and IP:port with credentials.
Replace with typed placeholders like `[REDACTED:AWS_KEY]` so meaning survives. Keep a stable per-document pseudonym
for emails ("<person-3>") ONLY IF level=="pseudonymize"; default masks to `[REDACTED:EMAIL]`.
Never log or persist original values; redaction_event stores only rule + count + masked sample ("sk_test_****").
Preserve text length mapping NOT required, but preserve newlines/markdown structure.
Provide `scan_report(project)` used later by the Governance UI.

Tests: table-driven for every rule incl. false-positive guards (commit SHAs, UUIDs, file hashes must survive),
all planted ground-truth secrets are caught (read ground_truth.json), idempotence (redact(redact(x)) == redact(x)),
and a performance test (1MB in < 1s).
Acceptance: 100% of planted secrets redacted, 0 SHAs/UUIDs damaged.
```

### P07: LLM layer (live + replay)

```
Read CLAUDE.md. Implement backend/app/llm.py.

API: `llm.structured(task: str, system: str, user: str, schema: type[BaseModel], *, max_tokens, temperature=0) -> BaseModel`
and `llm.text(...)`.
- Providers: anthropic (tool-use / JSON mode), openai (response_format json_schema), and `replay`.
- Always validate output with the Pydantic schema; on validation error retry up to 2 times with the error message
  appended; then raise LLMOutputError.
- Replay cache: sqlite table llm_cache(key = sha256(provider-agnostic task + system + user + schema json), response json).
  Modes: LLM_PROVIDER=replay -> cache hit required (miss => raise with a clear "no recording" error);
  live providers -> write-through cache. Add CLI `python -m app.llm record` that runs the pipeline on the seed dataset
  live and stores recordings in backend/seed/llm_recordings.json, committed to the repo so judges can run without a key.
  On startup in replay mode, bulk-load recordings into llm_cache.
- Safety: a `prompt_guard()` wrapper that wraps all artifact text in <untrusted_data> tags and puts a system rule that
  content inside is DATA not instructions (defends against prompt injection planted in Slack/commit text). Add a seeded
  injection string in the dataset (e.g. "ignore previous instructions") and test that it does not alter output.
- Budgeting: per-job token counter, hard cap via env, timeouts (60s), exponential backoff on 429/5xx.
- Fake `MockLLM` for unit tests that returns canned schema-valid objects.

Tests with MockLLM: retry-on-invalid-JSON, cache hit/miss, injection string stays quoted, budget cap raises.
Acceptance: all tests pass without any API key.
```

### P08: Reconstruct: entities, graph, temporal model (RECONSTRUCT)

```
Read CLAUDE.md. Implement backend/app/reconstruct/*.

1. entities.py: entity resolution for people. Merge aliases across platforms using deterministic signals first
   (same email, GitHub login <-> Slack handle map from a `identity_map` hint, normalized name, edit distance <= 1 on
   normalized names) and put low-confidence merges (< 0.8) into an ambiguity of type low_evidence instead of silently merging.
   Modules/services: derive from file paths (top-level dirs/packages) + ticket components. Output `entity` rows + set
   artifact.author_entity_id.
2. graph.py: build nodes/edges from artifacts: AUTHORED, REFERENCES (PR<->issue<->commit via keys like PAY-142, #89, SHAs),
   OWNS (module -> person by commit share >= 60% in last 90 days, else "shared"), DEPENDS_ON (imports/config references,
   keep simple: parse requirements/package.json + service names mentioned in docs), BLOCKS (issue links).
   Provide graph queries as SQL recursive CTEs: `module_dependencies(module_id)`, `timeline(project_id, from, to)`,
   `bus_factor(project_id)`.
3. authority.py: `authority_for(artifact)`, and `resolve(claims_a, claims_b)` that orders by valid_time then authority.
   Rule: newer + higher/equal authority supersedes older; newer but LOWER authority does NOT supersede (it becomes a
   conflict to review). Same-time, same-authority disagreement => UNRESOLVED.
4. extract.py: LLM extraction step. For each module/time window, batch relevant artifacts (selected via the graph and
   FTS, never the whole corpus) and call llm.structured with schema `ExtractedFacts{claims[{kind,text,evidence_ids,
   valid_time,confidence}]}`. Evidence IDs MUST be from the provided artifact list (the validator in P09 enforces this).
   Create `decision` nodes with valid_from/valid_to, and SUPERSEDES edges using authority.resolve.
Everything writes to node/edge with tx_from=now (bi-temporal).

Tests: alias merging on seed data (Aarav's 4 aliases -> 1 entity), scenario 1 & 2 produce SUPERSEDES edges, scenario 3
produces an UNRESOLVED flag, bus_factor flags `ledger-sync`.
Acceptance: after running on seed data, the graph contains the expected nodes/edges from ground_truth.json.
```

### P09: Verify: citations, conflicts, ambiguity ledger (VERIFY)

```
Read CLAUDE.md. Implement backend/app/verify/*.

- citations.py: `bind_and_validate(claim)`:
  * every evidence_id must exist in the artifact table for this project,
  * snippet must be a real substring (normalized whitespace) of artifact.body_redacted; if the LLM paraphrased, locate the
    best matching span with a sliding-window fuzzy match (difflib ratio >= 0.85) and replace with the REAL substring + offsets,
  * compute source_uri deep link (commit URL / PR permalink / ticket key / doc path#offset),
  * claim with no valid evidence => rejected (status=rejected, reason="no_valid_evidence"), counted in the scorecard.
  * sensitivity = max(evidence.sensitivity).
- conflicts.py: pairwise contradiction detection on claims touching the same subject key (module+topic): first
  deterministic rules (numeric mismatch like retry 3 vs 5, same key different value), then ONE batched llm.structured call
  per subject for the ambiguous ones with schema `{relation: entails|contradicts|unrelated, rationale, confidence}`.
  Apply authority.resolve: higher-authority newer wins -> create SUPERSEDES/CONTRADICTS edge and mark the stale claim
  `needs_review` with a "superseded by" pointer; same-time conflicts => ambiguity(type=conflict, severity=high).
- ambiguity.py: detectors (deterministic) for: orphan_branch (unmerged branch with commits in last 60 days),
  unclosed_thread (question with no reply after N days / outgoing person tagged without answer),
  undocumented_module (module with >N commits, no doc references), stale_config (env var referenced but absent in
  latest config or tagged _OLD/_DEPRECATED), missing_doc (open blocker with no runbook), low_evidence (claims with only
  chat evidence).
- scorecard.py: completeness scorecard: % claims with evidence, % modules documented, open ambiguities by severity,
  contradictions resolved/unresolved, coverage of open PRs/issues/branches, "epistemic confidence" per claim =
  f(authority of evidence, number of independent sources, recency, unresolved conflict penalty), and an overall 0-100 score
  with the formula documented in docs/SCORING.md.

Tests: each seed scenario (1-10) is detected exactly as in ground_truth.json; fabricated evidence is rejected;
paraphrased snippets are repaired to real substrings.
Acceptance: pytest green; scorecard JSON for seed data matches expected thresholds.
```

### P10: Pipeline orchestration + jobs + SSE

```
Read CLAUDE.md. Implement jobs.py and routers/handovers.py (creation + pipeline run).

- POST /projects/{id}/handovers {outgoing_user_id, successor_user_id, lead_user_id, due_date, notes} creates a handover.
- POST /handovers/{id}/run starts a background job running stages in order and updating job.stage/progress:
  connect_check -> redact_audit -> entities -> graph -> extract -> verify_citations -> conflicts -> ambiguities ->
  scorecard -> draft_plan -> snapshot_v1. Each stage is idempotent and resumable (re-run replaces draft claims that
  have origin llm/rule and status draft, but NEVER overwrites human-edited/accepted claims).
- GET /jobs/{id} and GET /jobs/{id}/events (Server-Sent Events) for live progress with stage names and counts
  ("Extracted 42 claims", "Rejected 3 unsupported claims").
- Failure handling: a failed stage marks the job failed with a readable error and keeps earlier results; "Retry from stage"
  supported. Concurrency: one active job per handover.
- draft_plan: llm.structured creates Day 1-7/8-14/15-30 plan_items, each linked to claim_ids (validator drops items
  with no linked claims).
- Create handover_version v1 (see P11) when the draft completes; handover.status -> in_review.

Tests: full pipeline on seed data using replay/MockLLM finishes < 60s; rerun doesn't duplicate; human edits survive rerun.
Acceptance: single curl sequence (login -> load demo -> create handover -> run -> poll) yields an in_review handover with claims.
```

### P11: Review API, versioning, dual sign-off

```
Read CLAUDE.md. Implement handover/claims.py, versions.py, signoff.py and routers/review.py.

- GET /handovers/{id}/claims?section=&status=&kind=&min_sensitivity= (paginated), PATCH /claims/{id}
  (edit text -> status=edited, origin stays but edited_by set; accept; reject with required reason; "needs_review"),
  POST /handovers/{id}/claims (human-added claim: requires >=1 evidence artifact id OR explicit
  `unverified=true` which renders as "Unverified (author-asserted)").
- Ambiguity endpoints: list, resolve (resolution_note required), waive (reason + only lead).
- Optimistic concurrency via `version`/`updated_at` check -> 409 on stale edit.
- Versioning: `POST /handovers/{id}/snapshot` freezes all current claims+ambiguities+plan into handover_version
  with hash = sha256(prev_hash + canonical_json(snapshot)). GET /handovers/{id}/versions, GET diff between two
  versions (added/removed/changed claims with word-level diff for text).
- Sign-off: POST /handovers/{id}/signoff {version, comment}. Allowed only for outgoing + lead, only on the latest
  snapshot, blocked if open HIGH-severity ambiguities remain (unless waived by lead) or any claim is still `draft`
  (must be accepted/edited/rejected). Signature = HMAC-SHA256(SECRET_KEY, handover_id|version|hash|user_id|timestamp).
  When BOTH roles signed the same version -> status=signed. Any later edit invalidates sign-offs and requires a new
  snapshot (return clear message). GET /handovers/{id}/verify returns {chain_valid, signatures_valid}.
- Every mutation writes audit_log via audit().

Tests: state machine (can't sign with drafts, can't sign stale version, both signatures required, edit invalidates),
diff correctness, chain verification fails if snapshot JSON is altered in DB.
Acceptance: pytest green.
```

### P12: Role-scoped views, plan, receipts, copilot, export

```
Read CLAUDE.md. Implement handover/views.py, plan.py, copilot.py, export.py and routers/portal.py.

- GET /handovers/{id}/view?as=<role|user> : builds the successor-facing view from the LATEST SIGNED version only.
  Applies policy.mask_claim per viewer. Views: maintainer (full), junior (adds "why it matters" glossary, hides nothing
  above clearance), contractor (clearance<=1, credentials/private escalations masked), auditor (metadata + scorecard +
  audit chain, no bodies). Only the lead can preview "view as" another role; successor sees only their own.
  Delivery: POST /handovers/{id}/deliver (lead only, requires status=signed) -> status=delivered, successor notified in-app.
- Plan: GET/PATCH /handovers/{id}/plan (move items between statuses, assign, add custom item). Each item shows linked claims.
- Receipts: POST /handovers/{id}/receipts {section, note?} acknowledgement per section; GET progress %
  (visible to lead + outgoing).
- Copilot: POST /handovers/{id}/chat {message} -> retrieval = FTS5 over artifact bodies AND claim text, filtered in SQL by
  effective clearance (firewall), top-k 8, then llm.structured with schema `{answer, citations[{artifact_id|claim_id,snippet}],
  can_answer: bool}`. Validator drops citations that weren't in the retrieved set; if can_answer is false or zero valid
  citations remain => deterministic refusal text: "I can't verify this from the handover evidence. Here's what is missing: ..."
  and suggests asking the outgoing contributor (creates an optional "open question" item). Streaming via SSE token events
  optional; non-streaming acceptable. Persist chat_message with refused flag.
- Export: GET /handovers/{id}/export?format=md|json|html. MD/HTML include citations as footnotes with permalinks, scorecard,
  signatures and hash. HTML is print-optimized so "Print to PDF" yields a clean document (no extra PDF library).

Tests: contractor never receives clearance-2 text anywhere (view, chat context, export) - assert by scanning responses for
planted confidential strings; copilot refuses on a question about an undocumented topic; copilot answers PAY-142 question with
valid citations; export contains hashes.
Acceptance: pytest green; the firewall test passes.
```

### P13: Backend hardening and API docs

```
Read CLAUDE.md. Hardening pass on backend only:
- Pydantic response models for every endpoint (no leaking internal columns like password_hash, acl internals).
- Pagination + sorting params standardized ({items,total,page,page_size}).
- Authorization check on EVERY route through a dependency (write a test that enumerates all routes and fails if one lacks
  an auth dependency except /health and /auth/login).
- Input limits (string lengths), file upload validation, CORS config from env, security headers middleware
  (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, a strict CSP for the SPA).
- Consistent error codes, request-id in logs and error responses.
- OpenAPI tags and examples; docs available at /api/docs only when ENV=dev.
- Global timeouts for long endpoints; make sure DB sessions never leak (test with 50 parallel requests).
- A `python -m app.cli` with commands: seed, reset-db, record-llm, verify-chain, create-user.
Acceptance: pytest green including the "all routes protected" test and parallel request test; ruff clean.
```

### P14: Frontend foundation and design system

```
Read CLAUDE.md (UI principles). Build the frontend shell. Use the `frontend-design` skill thinking: this should feel
polished and distinctive, not a default template.

- Tokens: Tailwind config + CSS variables (light/dark), type scale, spacing, radius, shadows. Status colors: verified (green),
  needs-review (amber), conflict (red), unverified (slate), sensitivity levels (0-3) as subtle badges with lock icons.
- Layout: left collapsible sidebar (Projects, Handovers, Governance, Settings), top bar (breadcrumbs, command palette trigger
  Cmd/Ctrl+K, theme toggle, user menu with role+clearance badge), content area with max-width and consistent page headers.
- Command palette (cmdk via shadcn Command): jump to handover/page, switch view role (lead only).
- API layer: src/lib/api/client.ts (fetch wrapper, cookie auth, error normalization, 401 -> redirect to /login),
  typed hooks per resource with TanStack Query, shared query keys, optimistic updates where safe.
- Auth pages: Login with "Demo accounts" cards (one click fill), protected routes, role-aware nav.
- Shared components: PageHeader, StatCard, StatusBadge, SensitivityBadge, EmptyState, ErrorState (with retry), Skeletons,
  ConfirmDialog, Kbd, CopyButton, RelativeTime (with absolute tooltip), CitationPill (see P17), JobProgress.
- Toasts via sonner for every mutation (success/error). Global ErrorBoundary. 404 page. Page title updates per route.
- Add a Storybook-lite route /dev/components (dev only) showing all shared components in light/dark.
Acceptance: login works against the backend, nav is role-aware, dark mode persists, typecheck+build pass, Lighthouse
accessibility >= 95 on login and dashboard.
```

### P15: Frontend: Dashboard, Projects, Connect and pipeline run

```
Read CLAUDE.md. Build these pages (all with loading/empty/error states):

1. Dashboard: cards for handovers by status, "needs your action" list (sign-offs pending, ambiguities assigned,
   unacknowledged sections), recent activity feed from audit_log.
2. Projects list + project detail: sources panel (cards per source with type icon, status, last sync, counts), "Add source"
   wizard (stepper): choose type (GitHub / Jira JSON / Slack JSON / Markdown & docs / **Load PayFlow demo**), configure or
   drag-and-drop upload with progress and validation messages, review what will be ingested, run. For GitHub: repo url + optional token
   field with a clear note that tokens are never stored/logged (or kept only in session).
3. Redaction transparency panel: table of redaction rules fired with counts (no original values), reassurance copy,
   "re-scan" button.
4. Create Handover dialog: select outgoing, successor, lead (dropdowns of project members), due date, notes.
5. Pipeline run screen: vertical stepper for the 11 stages with live SSE progress, per-stage counts, animated active state,
   elapsed time, collapsible log, retry-from-stage on failure, and a success state with a "Start review" CTA. Handles refresh
   (resumes from job id) and SSE disconnects (auto-reconnect/poll fallback).
Acceptance: from a fresh DB a user can: login -> load demo -> create handover -> run pipeline -> land on review, with no console errors.
```

### P16: Frontend: Review Studio (the centerpiece)

```
Read CLAUDE.md. Build /handovers/:id/review, the Split-Screen HITL Workbench. This is the most important screen: make it excellent.

Layout (3 resizable panes, remembering sizes in localStorage):
- LEFT: outline/filters: sections (Architecture, Ownership, Blockers, Open Work, Runbooks, Risks, Contacts, Dependencies),
  counts, filters by status/kind/sensitivity/confidence, search box, "Only needs attention" toggle, progress ring
  (reviewed/total).
- CENTER: claim cards. Each shows text (inline-editable via contentEditable-free textarea), StatusBadge, ConfidenceMeter
  (tooltip explaining the score), SensitivityBadge, inline CitationPills, buttons Accept / Edit / Reject (reject requires
  a reason popover), and a "superseded by / supersedes" ribbon with link. Edited claims show a word-level diff vs the
  original AI text (toggle). Keyboard: j/k move, a accept, e edit, x reject, / focus search, ? shows shortcut help.
  Bulk actions: accept all high-confidence verified in view (with confirm + count).
- RIGHT: Evidence & Issues drawer with tabs: Evidence (the exact source snippet with highlighted span, source metadata, a
  link out to the permalink, "show full artifact" with redactions visibly marked), Ambiguity Ledger (cards with severity,
  resolve/waive flow requiring notes), Conflicts (side-by-side older-vs-newer claim with authority weights and the chosen
  resolution; Accept resolution / Keep both / Edit), Scorecard (gauges + breakdown).
- Footer bar: unsaved-changes indicator, "Create snapshot", version selector with a Diff modal (added/removed/changed), and a
  "Request sign-off" button whose disabled state explains exactly what's blocking (X drafts, Y high-severity ambiguities).
- Sign-off modal: shows version hash (short), summary checklist, comment, and a clear "I confirm" action. After signing,
  shows both signers' status chips and the verify-chain result.
- Concurrency: handle 409 by showing a non-destructive "this claim changed, review" banner.
- Autosave drafts of edits, optimistic updates with rollback + toast on failure.
Acceptance: a reviewer can clear every draft claim and ambiguity using only the keyboard; blocked sign-off explains reasons;
the Evidence tab opens in < 100ms from cache; no layout shift when switching claims.
```

### P17: Frontend: Citation pills, Timeline and Dependency graph

```
Read CLAUDE.md. Build:

1. CitationPill component: compact chip with kind icon + label ([PR #142], [Commit a8f9d2], [PAY-142], [Slack #backend-dev],
   [ADR-003]). Hover = popover with snippet preview + date + authority badge; click = opens the Evidence drawer on that artifact
   (works inside Review, Portal and Copilot via a shared EvidenceDrawerProvider). Pills for restricted evidence render as
   locked "Restricted" chips with no content.
2. Decision Timeline page/tab (React Flow or custom SVG swimlane, pick the simpler robust option): lanes per module/topic,
   x-axis time with zoom/pan, nodes = decisions/blockers/PRs, SUPERSEDES drawn as arrows with the old node faded and
   struck through, UNRESOLVED conflicts as red dashed links, tooltips and click-through to evidence, filter by module and date
   range. Provide a text-equivalent list view for accessibility.
3. Dependency topology map (React Flow): modules/services as nodes sized by commit share, colored by owner, badge for bus-factor
   risk and undocumented, edges for DEPENDS_ON/BLOCKS; click a node => side panel with owner, claims, open work, risk. Auto layout
   with dagre (only add this dependency if needed), minimap, fit-view, search-to-focus.
4. Both visualizations read from GET /handovers/{id}/graph and /timeline (add these endpoints if missing, respecting clearance filtering).
Acceptance: seed data renders the Redis->JWT and MongoDB->Postgres supersession visibly, the unresolved rate-limit conflict
appears in red, and `ledger-sync` shows a bus-factor warning. Smooth at 300 nodes.
```

### P18: Frontend: Successor Handover Portal, Day 1-30 board and Copilot

```
Read CLAUDE.md. Build /handovers/:id/portal (the successor's home) and related views.

- Landing: welcome header with outgoing person's name, handover date, trust strip (signed by X and Y, version hash, verified
  chip), overall readiness/acknowledgement ring.
- Role view switcher (segmented control: Maintainer / Junior / Contractor / Auditor), visible only to the lead (preview mode,
  clearly bannered "Previewing as Contractor"); successors see only their own view.
- Sections as readable, editorial cards with inline citation pills, restricted items shown as masked placeholders, and an
  "I've read and understood" acknowledgement button per section (calls receipts API, optional note), with a progress bar.
- Day 1-30 Execution Board: 3 columns (Day 1-7, 8-14, 15-30), draggable cards (use native HTML5 drag or @dnd-kit only if
  needed), priority tags, linked claims on card detail drawer, status todo/doing/done, add custom task.
- "Known Unknowns" tab: open ambiguities in plain language, each with "Ask Aarav" button that opens a prefilled question
  (stored as an open question; shows up on the outgoing person's dashboard).
- Grounded Copilot panel (right-side sheet, also a full page): chat UI with streaming-or-typing indicator, answers with
  CitationPills, a distinct refusal style ("I can't verify this...") with the missing-evidence explanation and "Ask outgoing
  owner" action, suggested starter questions generated from the plan, copy answer, thumbs up/down (stored), message history.
- Auditor view: scorecard, audit-chain verification result, signatures, redaction summary, no artifact bodies.
- Export menu (Markdown / JSON / Print-friendly HTML) and a print stylesheet.
Acceptance: logging in as Kabir (successor) shows only clearance-allowed content; Dev (contractor) cannot see any confidential
text anywhere including copilot answers; refusal path works; drag-and-drop persists after reload.
```

### P19: Governance, audit and admin screens

```
Read CLAUDE.md. Build /governance (lead + auditor only):
- Audit log table (filter by actor/action/date, expandable JSON payload, pagination) with a "Verify chain" button showing a clear
  pass/fail with the first broken sequence number if tampered.
- Policy matrix page: read-only table of role x clearance x what is visible, rendered from policy.py via GET /policy.
- Redaction report per project; sensitivity distribution chart (simple SVG/CSS bars, no chart library).
- Members management for a project (add/remove, set clearance within limits; only lead).
- Settings page: theme, timezone display, LLM mode indicator ("Live (model X)" or "Replay (recorded)"), with an
  explanation tooltip, and a "Danger zone" with reset demo data (confirm dialog, dev/demo only).
Acceptance: tamper test via CLI breaks chain and UI reports exactly that; non-privileged users get a polite 403 screen.
```

### P20: UX polish and "small things" pass

```
Read CLAUDE.md and Part D checklist in the plan. Do a full-app polish pass without adding new features:
- Walk every page in light and dark; fix spacing, alignment, truncation, overflow, focus order, contrast (WCAG AA).
- Add skeletons that match final layout (no layout jumps), optimistic UI where safe, debounced search, stable keys.
- Micro-interactions: button press states, card hover, drawer slide (150-200ms), progress ring animation, success checkmark on
  sign-off, subtle confetti-free celebration (clean "Handover delivered" state). Honor prefers-reduced-motion.
- Copy review: replace every technical error with a human message + next step; ensure terminology is consistent (claim,
  evidence, ambiguity, snapshot, sign-off).
- Responsive: test 1024/1280/1440 and a graceful 768 (panes collapse to tabs).
- Performance: route-level code splitting (React Flow only loads on graph pages), memoize heavy lists, virtualize the claim list
  if > 200 items, bundle analyzer budget (initial JS < 250KB gz).
- A11y: aria labels on icon buttons, live regions for toasts/job progress, keyboard traps in dialogs fixed, skip-to-content link.
- Favicon, app title, OG meta, loading splash, offline/API-down banner with retry.
Acceptance: axe has no critical/serious issues on main pages; Lighthouse perf >= 90 and a11y >= 95 on dashboard + review.
```

### P21: Tests (backend integration + e2e)

```
Read CLAUDE.md. Fill testing gaps:
- Backend: an integration test `test_golden_path.py` that runs end-to-end on seed data in replay mode and asserts against
  ground_truth.json: all 10 scenarios detected, 100% planted secrets redacted, zero claims without evidence persisted as
  verified, sign-off state machine, firewall (contractor sees none of the planted confidential strings anywhere), copilot
  refusal. Produce a metrics report (precision/recall of detected conflicts/ambiguities, hallucination rate = invalid-evidence
  claims / total) written to docs/EVAL_REPORT.md by `make eval`. This report doubles as Round 3's "testing report".
- Prompt-injection test (planted injection in Slack data must not change outputs).
- Frontend: Vitest for CitationPill label formatting, diff rendering, policy-based masking helpers.
- Playwright e2e (e2e/golden.spec.ts): login as Aarav -> load demo -> create handover -> run -> review (accept all, resolve
  ambiguities) -> snapshot -> sign as Aarav -> sign as Meera -> deliver -> login as Kabir -> view portal -> ask copilot a
  question (citations visible) -> ask an unanswerable question (refusal) -> login as Dev (contractor) -> verify masked content.
- CI runs backend tests + eval + frontend typecheck/build + Playwright headless.
Acceptance: all green in CI; EVAL_REPORT.md committed with real numbers.
```

### P22: Deployment (Docker, Render/Fly)

```
Read CLAUDE.md. Create deployment assets:
- Multi-stage Dockerfile: node:20-alpine builds frontend -> python:3.11-slim installs backend, copies dist, runs uvicorn with
  non-root user, healthcheck on /api/v1/health, volume at /app/data for SQLite + LLM cache.
- docker-compose.yml (single service, env file, volume), `docker compose up` yields the full app on :8000 with demo data seeded.
- render.yaml (or fly.toml) for a free-tier cloud deploy with a persistent disk; document the one-click steps.
- Env handling: documented .env.example; app fails fast with a clear message if SECRET_KEY is default in prod.
- Startup: run migrations, seed demo users + demo dataset only if DB empty and SEED_ON_START=true; load LLM recordings in replay mode.
- Backups: `python -m app.cli backup` copies the SQLite file safely (sqlite3 .backup API).
- Smoke script `scripts/smoke.sh` that curls health, logs in, loads demo, runs pipeline, and prints PASS/FAIL.
Acceptance: fresh clone -> `docker compose up --build` -> open http://localhost:8000 -> login with demo account -> full golden path
works with NO API key; cloud deployment reachable via public URL with the same behavior.
```

### P23: Documentation and judge-facing materials

```
Read CLAUDE.md. Write documentation:
- README.md: what/why (3 sentences), screenshot placeholders, 2-minute quickstart (Docker + local dev), demo accounts table,
  architecture diagram (mermaid) of the 5-stage pipeline, stack justification table (mapping dossier claims to implementation, as in
  Part A), env vars, folder tour, how replay mode works, how to run live with an API key, how to run tests/eval.
- docs/ARCHITECTURE.md (data model ERD in mermaid, temporal model, authority resolution examples, firewall design),
  docs/POLICY.md, docs/SCORING.md, docs/SECURITY.md (threat model: prompt injection, secret leakage, privilege escalation,
  tampering, what is NOT covered), docs/EVAL_REPORT.md (generated), docs/DEMO_SCRIPT.md (from the plan's Part E), docs/LIMITATIONS.md
  (honest list: SQLite scale, no SSO, regex-based redaction limits, LLM variability).
- Make sure README claims match what the code really does (re-verify each claim against the code; remove or soften anything not true).
Acceptance: a new developer can run everything from the README in under 5 minutes; no claim in docs lacks a code path.
```

### P24: Final QA, demo hardening, and Round-3 upgrade gates

```
Read CLAUDE.md. Final verification sweep:
1. Fresh-clone test on a clean machine/container following README exactly; fix any gap.
2. Run the full demo script (docs/DEMO_SCRIPT.md) 3 times in a row from a reset DB; time it (target <= 6 min); fix flakiness.
3. Kill the network (simulate no LLM key and no internet) and confirm replay mode runs the full flow.
4. Chaos checks: refresh mid-pipeline, double-click sign-off, two reviewers editing the same claim, expired JWT mid-session,
   oversize upload, malformed JSON upload, GitHub rate-limit error, SSE disconnect. Each must degrade with a clear message.
5. Security checks: confirm secrets absent from DB (grep for planted fake secrets in the SQLite file and logs), CSP works, cookies
   flags correct, all routes authorized, contractor/auditor leak tests pass.
6. Produce docs/ROUND3_UPGRADE_CHECKLIST.md mapping the three committed upgrades (Multi-Role ABAC view switcher, NLI-style
   code-vs-doc conflict engine, Grounded copilot + interactive dependency graph) to the exact files/tests that prove each,
   plus any known gaps.
7. Tag v1.0.0, record a 3-minute walkthrough checklist (shots list), and export final screenshots.
Acceptance: all checks pass or are listed honestly in LIMITATIONS.md.
```

---

## PART D: "Small things" checklist (verify before submitting)

**Product / data**
- [ ] Idempotent re-ingestion; duplicate uploads don't duplicate artifacts
- [ ] Soft delete of sources; deleting a source doesn't orphan claims silently (warn)
- [ ] Human edits survive pipeline re-runs
- [ ] Any edit after sign-off invalidates sign-offs and requires a new snapshot
- [ ] Claims from restricted evidence inherit the highest sensitivity
- [ ] Redaction never stores originals; logs contain no secrets
- [ ] Prompt-injection text is treated as data
- [ ] Time zones: stored UTC, displayed local (IST for your team), absolute time on hover

**UI/UX**
- [ ] Skeleton, empty, and error state on every data view
- [ ] Toasts on every mutation; confirm dialogs on destructive actions
- [ ] Unsaved-changes guard; autosave of edits
- [ ] Keyboard shortcuts + `?` help; focus rings; Esc closes drawers
- [ ] Copy buttons on IDs/hashes; short hash with full hash on hover
- [ ] Dark mode persisted; reduced-motion respected
- [ ] Print stylesheet for the handover; export MD/JSON/HTML
- [ ] Favicon, titles, 404 page, API-down banner, session-expiry message
- [ ] "Previewing as ..." banner during view-as mode

**Engineering**
- [ ] Every route authorized (test enforces it); rate limit on login
- [ ] Standard error shape; request-id in logs
- [ ] CORS/CSP/security headers; non-root container; healthcheck
- [ ] Replay mode works with zero network and zero keys
- [ ] `.env.example` complete; fail-fast on default SECRET_KEY in prod
- [ ] CI green; EVAL_REPORT.md has real numbers
- [ ] README claims match the code

---

## PART E: Demo script (about 5 minutes)

1. **Problem (20s):** Aarav leaves mid-refactor, and the knowledge is scattered.
2. **Connect (40s):** Log in as Meera (lead), click *Load PayFlow demo*, and show the redaction panel with secrets masked and no originals stored.
3. **Reconstruct and Verify (60s):** Run the pipeline and watch the live stages. Open the timeline and show Redis→JWT and MongoDB→Postgres superseded, plus the red unresolved rate-limit conflict.
4. **Review (90s):** In the Review Studio, click a citation pill to see the exact snippet. Reject one unsupported claim, edit another and show the word diff, then resolve the orphan-branch ambiguity. Show the sign-off button's blocking reasons, then snapshot and sign as Aarav and Meera.
5. **Handover (90s):** Deliver, log in as Kabir, and show the Day 1–30 board and the copilot answering PAY-142 with citations. Ask something undocumented to show the refusal. Log in as Dev (contractor) to show masked confidential items. Show the auditor's chain verification.
6. **Close (20s):** Show the eval report numbers, namely the hallucination rate and the secret redaction rate.

---

## Suggested team split (matches your roles)

| Member | Prompts |
|---|---|
| Shravan (lead/architect) | P01, P02, P10, P11, P16, P22, P24 |
| Rajas (backend/ingestion) | P03, P05, P06, P13, P12 (policy/export parts) |
| Ritdham (AI/GraphRAG) | P04 (ground truth), P07, P08, P09, P12 (copilot) |
| Om (UI/QA) | P14, P15, P17, P18, P19, P20, P21, P23 |

Run P01 → P03 serially first, then parallelize backend (P05-P09) and frontend (P14-P15) across agents, rejoining at P10/P16.
