# RelayOps 5-Minute Judge Demo Walkthrough

This demo script provides a step-by-step, minute-by-minute guide for presenting RelayOps to judges, technical evaluators, and engineering leadership. It demonstrates every core capability: multi-source ingestion, secret redaction, temporal graph reconstruction, split-screen human review, dual cryptographic sign-off, successor onboarding, grounded Copilot with deterministic refusal, and pre-inference permission firewalling.

---

## Demo Overview & Persona Credentials

| Persona | Name | Email | Password | Role | Clearance | Demo Purpose |
|---|---|---|---|:---:|:---:|---|
| **Lead / Manager** | Meera Patel | `meera@payflow.dev` | `password123` | `lead` | 3 | Ingestion, pipeline execution, administrative review, sign-off & delivery |
| **Outgoing Lead Backend** | Aarav Kulkarni | `aarav@payflow.dev` | `password123` | `outgoing` | 2 | Claim review, word-level diff, resolving ambiguities, snapshot sign-off |
| **Successor Engineer** | Kabir Sharma | `kabir@payflow.dev` | `password123` | `successor` | 1 | Onboarding portal, Day 1-30 Kanban, reading receipts, Copilot Q&A |
| **External Contractor** | Dev Mukherjee | `dev@payflow.dev` | `password123` | `contractor` | 1 | Demonstrating pre-inference SQL firewall & masked confidential claims |
| **Compliance Auditor** | Sana Chen | `sana@payflow.dev` | `password123` | `auditor` | 1 | Cryptographic SHA-256 audit log verification |

---

## ⏱️ Minute 0:00 – 0:20 | The Problem

**Spoken Script:**
> *"When a senior engineer leaves a team, critical knowledge is scattered across hundreds of git commits, closed PRs, Jira tickets, private Slack channels, and stale documentation. Traditional handovers fail because docs rot instantly and conversational AI assistants hallucinate ungrounded summaries.*
>
> *RelayOps solves this by turning messy, multi-source activity into a traceable, human-verified handover blueprint where every single claim is cryptographically backed by real artifact evidence."*

**Visual Action:**
- Open browser at `http://localhost:8000` (or `http://127.0.0.1:8000`).
- Point out the calm, developer-tool editorial interface and the instant **Demo Accounts** selector.

---

## ⏱️ Minute 0:20 – 1:00 | Stage 1: Connect & Ingestion Transparency

**Spoken Script:**
> *"Let's log in as Meera, our engineering team lead. Our backend lead Aarav is departing mid-way through a critical payment webhook refactor.*
>
> *We connect our scattered sources: GitHub repositories, Jira issues, Slack engineering channels, and architecture markdown docs. Notice what happens during ingestion: before any data is persisted to SQLite and before any token touches an LLM, our in-memory redaction engine scrubs all secrets and PII."*

**Step-by-Step Actions:**
1. Click **Meera Patel (Lead)** on the login screen $\rightarrow$ redirects to `/dashboard`.
2. Navigate to **Projects** $\rightarrow$ click **PayFlow** $\rightarrow$ select **Sources** tab.
3. Show the connected sources:
   - `github`: 80 commits, 25 PRs, 2 unmerged branches.
   - `jira_json`: 15 issue tickets.
   - `slack_json`: `#backend-dev`, `#incidents`, `#leads-private`.
   - `markdown`: ADR-003, RFC-007, Runbooks.
4. If sources are empty, click **Add Source** $\rightarrow$ select **Load PayFlow demo** $\rightarrow$ run.
5. Click **Redaction Transparency Panel**:
   - Point out the scrubbed rule counts: AWS keys, Stripe secret keys (`sk_test_...`), Bearer tokens, DB connection strings, and compensation figures.
   - Emphasize the reassurance notice: *"Only masked samples (e.g. `sk_test_...abcd`) are logged for compliance; original plaintext secrets were scrubbed in-memory and never written to disk."*

---

## ⏱️ Minute 1:00 – 2:00 | Stages 2 & 3: Reconstruct & Verify

**Spoken Script:**
> *"Now we trigger the pipeline. RelayOps builds a bi-temporal knowledge graph that links commits, pull requests, decisions, and people. It computes author ownership using git blame shares, extracts candidate claims, and runs them through our citation validator.*
>
> *Crucially, RelayOps does not smooth over gaps. It uses a source authority hierarchy—where production code beats issue tickets, which beat design docs, which beat chat—to automatically detect supersessions and surface open contradictions in the Ambiguity Ledger."*

**Step-by-Step Actions:**
1. Click **Run Pipeline** (or inspect completed run).
2. Show the real-time stage progress: `CONNECT` $\rightarrow$ `RECONSTRUCT` $\rightarrow$ `VERIFY` $\rightarrow$ `REVIEW` $\rightarrow$ `HANDOVER`.
3. Navigate to **Timeline** (`/handovers/:id/timeline`):
   - **Superseded Decision 1:** Point to `ADR-003` (Redis session caching, Oct 12). Show how it is visually faded and struck through with a `SUPERSEDES` arrow pointing to `PR #89` (stateless JWT authentication, Nov 2).
   - **Superseded Decision 2:** Show MongoDB discussion superseded by PostgreSQL migration PR.
   - **Unresolved Contradiction:** Point to the red dashed link between two contemporaneous Slack messages debating the payment provider rate limit (100 req/min vs 500 req/min). Note that because both are chat with equal authority and no code resolution, RelayOps flags it as `UNRESOLVED`.
4. Navigate to **Dependency Topology** (`/handovers/:id/topology`):
   - Show interactive React Flow graph of modules and services.
   - Click module `ledger-sync`: show that Aarav authored 85% of commits, highlighting a critical bus-factor risk.

---

## ⏱️ Minute 2:00 – 3:30 | Stage 4: Review Studio & Dual Sign-Off

**Spoken Script:**
> *"Now we enter the centerpiece: the Review Studio. This is the split-screen Human-in-the-Loop workbench where the outgoing engineer and lead verify what the system extracted.*
>
> *Every claim has an epistemic confidence score and clickable citation pills. When an engineer edits a claim, RelayOps computes a word-level diff and resets approvals. And before a handover can be delivered, both Aarav and Meera must cryptographically sign off on the exact same snapshot."*

**Step-by-Step Actions:**
1. Switch user to **Aarav Kulkarni (Outgoing)** using the user menu or quick login.
2. Navigate to `/handovers/:id/review`:
   - Point out the 3 resizable panes: Outline & filters left, Claim cards center, Ambiguity Ledger & Evidence right.
3. **Inspect Citation Substring Binding:**
   - On claim *"Authentication uses stateless JWT tokens to avoid Redis operational overhead"*, click the **`[PR #89]`** citation pill.
   - The slide-over **Evidence Drawer** opens, scrolling directly to the exact substring match in the PR body.
4. **Edit Claim & Word-Level Diff:**
   - Click **Edit** on an accepted claim.
   - Add note: *"Requires rotating the webhook signing secret in Stripe dashboard before Dec 1."*
   - Save. Click **Show Diff**: toggle the clean green/red LCS word diff showing exact additions and removals.
5. **Resolve an Ambiguity:**
   - In the Ambiguity Ledger pane, select the high-severity `orphan_branch` item for `feature/webhook-retry-v2`.
   - Click **Resolve**: Enter note *"Logic superseded by idempotency headers; branch can be deleted."*
6. **Dual Cryptographic Sign-Off:**
   - Click **Create Snapshot**: generates Version 1.0 snapshot with SHA-256 hash `sha256:...`.
   - Click **Sign Off as Aarav**: HMAC signature submitted. Status remains `in_review` (awaiting lead).
   - Log out and log in as **Meera Patel (Lead)**.
   - Go to Review Studio $\rightarrow$ inspect snapshot $\rightarrow$ click **Sign Off as Meera**.
   - With both signatures recorded on the matching hash, status transitions to `signed` $\rightarrow$ click **Deliver Handover**.

---

## ⏱️ Minute 3:30 – 4:40 | Stage 5: Successor Portal & Grounded Copilot

**Spoken Script:**
> *"Now let's switch to Kabir, our incoming junior engineer on Day 1. Kabir is greeted by an editorial onboarding portal with a trust strip, reading receipts, a 30-day execution roadmap, and our grounded Copilot.*
>
> *The Copilot is strictly bounded by a pre-retrieval SQL clearance firewall: it only answers from verified evidence and deterministically refuses to hallucinate when evidence is missing."*

**Step-by-Step Actions:**
1. Log in as **Kabir Sharma (Successor)** $\rightarrow$ navigate to `/handovers/:id/portal`.
2. **Trust Strip & Section Receipts:**
   - Point to the header: signed by Aarav & Meera, snapshot hash, readiness score.
   - Scroll to the Architecture section $\rightarrow$ click **"I've read and understood"**: receipt recorded with timestamp.
3. **Day 1-30 Execution Board:**
   - Switch to the Day 1-30 tab: show tasks grouped into `Day 1-7`, `Day 8-14`, and `Day 15-30`.
   - Drag a task from `todo` to `doing`. Click task detail to view the linked verified claim.
4. **Grounded Copilot Verification:**
   - Open the Copilot drawer.
   - Ask: *"What is blocking vendor sandbox access?"*
   - Copilot answers accurately, citing `[PAY-142]` with the exact evidence snippet.
5. **Deterministic Refusal on Missing Evidence:**
   - Ask: *"How do we deploy the Kubernetes ingress controller?"*
   - Copilot responds with deterministic refusal:
     > *"I can't verify this from the handover evidence. Here's what is missing: Direct artifact evidence for this topic. I suggest asking the outgoing contributor to clarify."*
   - Emphasize to the judges: **Zero hallucination.**

---

## ⏱️ Minute 4:40 – 5:10 | Multi-Role ABAC & Contractor Isolation

**Spoken Script:**
> *"What about external contractors? Let's log in as Dev, our third-party contractor with clearance 1. Our pre-retrieval SQL firewall guarantees that confidential vendor contacts and private channel discussions are completely invisible."*

**Step-by-Step Actions:**
1. Log in as **Dev Mukherjee (Contractor)** $\rightarrow$ open `/handovers/:id/portal`.
2. Show that confidential claims (such as private partner escalation contacts) are rendered as masked placeholders:
   - `[Restricted: requires clearance 2]` with all evidence purged.
3. Ask the Copilot as Dev: *"Who is our private vendor contact?"*
   - The pre-retrieval SQL firewall filters out Level 2 artifacts entirely before the query reaches the LLM. Copilot politely refuses.

---

## ⏱️ Minute 5:10 – 5:30 | Governance, Audit Chain & Evaluation Report

**Spoken Script:**
> *"Finally, let's look at compliance with Sana, our compliance auditor. RelayOps records every redaction, edit, and sign-off in a rolling SHA-256 hash chain.*
>
> *In our benchmark evaluation against ground truth, RelayOps achieved 100% planted secret recall, 0.0% hallucination rate, and 100% evidence validity."*

**Step-by-Step Actions:**
1. Log in as **Sana Chen (Auditor)** $\rightarrow$ navigate to `/governance`.
2. View the cryptographic audit log table.
3. Click **Verify Chain**:
   - System traverses all sequence entries and confirms that all SHA-256 hashes are intact.
4. Open `docs/EVAL_REPORT.md` (or show governance metrics):
   - Highlight: 10/10 planted scenarios detected, 100% secret redaction recall, 0% hallucination rate.

**Closing Spoken Summary:**
> *"RelayOps replaces undocumented tribal knowledge with an immutable, verifiable chain of truth. Thank you!"*
