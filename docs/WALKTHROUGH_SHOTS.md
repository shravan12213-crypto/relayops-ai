# RelayOps 3-Minute Video Walkthrough & Shots List

This shot-by-shot checklist provides an exact script, visual timing, and screen actions for recording a high-impact, 3-minute video presentation or live demonstration of RelayOps.

---

## Shot Overview (Total Duration: 3:00)

```
0:00 ─── [Shot 1: The Problem & Dashboard] (0:15)
0:15 ─── [Shot 2: Connect & Zero-Leak Redaction] (0:25)
0:40 ─── [Shot 3: Live Pipeline Orchestration] (0:15)
0:55 ─── [Shot 4: Decision Timeline & Topology Graph] (0:25)
1:20 ─── [Shot 5: Review Studio & Word-Level Diff] (0:30)
1:50 ─── [Shot 6: Dual Cryptographic Sign-Off & Delivery] (0:20)
2:10 ─── [Shot 7: Successor Portal & Day 1-30 Board] (0:20)
2:30 ─── [Shot 8: Grounded Copilot & Deterministic Refusal] (0:15)
2:45 ─── [Shot 9: Multi-Role Firewall & Audit Chain Verification] (0:15)
3:00 ─── [End]
```

---

## Shot-by-Shot Walkthrough Script

### Shot 1: The Problem & Developer Context (0:00 – 0:15)
- **Persona:** Unauthenticated / Login Screen
- **URL:** `/login`
- **Visual:** Clean login screen displaying demo persona selectors (`Meera`, `Aarav`, `Kabir`, `Dev`, `Sana`).
- **Action:** Click **Meera Patel (Lead)** to log in with one click.
- **Spoken Audio:**
  > *"When key engineers leave, critical architecture knowledge is scattered across hundreds of PRs, Slack messages, and stale docs. RelayOps converts this scattered activity into an evidence-linked, human-verified handover blueprint. Let's log in as Meera, our engineering lead."*

---

### Shot 2: Connect & In-Memory Redaction Transparency (0:15 – 0:40)
- **Persona:** Meera Patel (Lead, Clearance 3)
- **URL:** `/projects/payflow`
- **Visual:** Project sources tab showing GitHub, Jira, Slack, and Markdown documentation.
- **Action:** Open **Redaction Transparency Panel**.
- **Spoken Audio:**
  > *"Notice what happens before any data touches SQLite or an LLM: our in-memory redaction engine scrubs 100% of API keys, AWS credentials, database passwords, phone numbers, and compensation figures. Only masked compliance samples are audited; plaintext secrets never reach disk."*

---

### Shot 3: Live Pipeline Execution (0:40 – 0:55)
- **Persona:** Meera Patel (Lead)
- **URL:** `/handovers/:id/pipeline`
- **Visual:** Real-time Server-Sent Events (SSE) stage cards updating sequentially: `connect_check` $\rightarrow$ `redact_audit` $\rightarrow$ `entities` $\rightarrow$ `graph` $\rightarrow$ `extract` $\rightarrow$ `verify_citations` $\rightarrow$ `conflicts` $\rightarrow$ `ambiguities` $\rightarrow$ `scorecard`.
- **Action:** Watch progress ring hit 100% and transition status to `in_review`.
- **Spoken Audio:**
  > *"We trigger the pipeline. RelayOps builds a bi-temporal knowledge graph, evaluates source authority, binds citations, and detects conflicts with real-time SSE progress."*

---

### Shot 4: Decision Timeline & Dependency Topology Map (0:55 – 1:20)
- **Persona:** Meera Patel (Lead)
- **URL:** `/handovers/:id/timeline` and `/handovers/:id/topology`
- **Visual:**
  - **Timeline:** ADR-003 (Redis sessions) visually faded and struck-through, superseded by PR #89 (stateless JWT). Red dashed link showing contemporaneous payment rate limit conflict (100 vs 500 req/min).
  - **Topology:** Interactive React Flow map of services; `ledger-sync` flagged with single-author bus-factor-1 risk.
- **Spoken Audio:**
  > *"On the Decision Timeline, production code overrides design docs: Redis caching is struck through with a SUPERSEDES link to PR #89. Meanwhile, contradictory chat claims are flagged as UNRESOLVED. In the topology map, bus factor risks are highlighted automatically."*

---

### Shot 5: Review Studio Workbench & Word-Level Diff (1:20 – 1:50)
- **Persona:** Aarav Kulkarni (Outgoing Lead Backend, Clearance 2)
- **URL:** `/handovers/:id/review`
- **Visual:** 3-pane split-screen workbench.
- **Action:**
  1. Click citation pill `[PR #89]`: slide-over Evidence Drawer highlights exact character substring match in PR body.
  2. Click **Edit** on a claim, add note: *"Rotate webhook secret before Dec 1"*.
  3. Toggle **Show Diff**: green/red LCS word-level diff renders.
  4. In the Ambiguity Ledger pane, resolve the orphan branch item for `feature/webhook-retry-v2`.
- **Spoken Audio:**
  > *"Now into the centerpiece: the Review Studio. Every claim has verified citation pills linking directly to artifact text. When Aarav edits a claim, RelayOps computes a word-level LCS diff and resets approvals. Aarav resolves the orphan branch ambiguity, preparing the handover for sign-off."*

---

### Shot 6: Dual Cryptographic Sign-Off & Delivery (1:50 – 2:10)
- **Persona:** Aarav (Outgoing) $\rightarrow$ Meera (Lead)
- **URL:** `/handovers/:id/review`
- **Visual:** Sign-off dialog displaying SHA-256 snapshot hash `sha256:...`.
- **Action:**
  1. Aarav clicks **Create Snapshot**, then submits HMAC signature. Status shows: *Awaiting lead signature*.
  2. Switch to Meera $\rightarrow$ Meera signs the identical snapshot hash $\rightarrow$ Status turns green: `signed`.
  3. Meera clicks **Deliver Handover**.
- **Spoken Audio:**
  > *"Our dual sign-off rule requires both Aarav and Meera to sign off on the exact same cryptographic version hash. Once both signatures are verified, Meera delivers the handover to our successor."*

---

### Shot 7: Successor Portal & Day 1-30 Execution Board (2:10 – 2:30)
- **Persona:** Kabir Sharma (Successor, Clearance 1)
- **URL:** `/handovers/:id/portal`
- **Visual:** Editorial handover layout with trust strip (signed by Aarav & Meera, version hash, verified chip).
- **Action:**
  1. Click **"I've read and understood"** on the Architecture section $\rightarrow$ progress ring advances.
  2. Switch to **Day 1-30 Board** tab $\rightarrow$ drag a task from `Day 1-7 (todo)` to `doing`.
- **Spoken Audio:**
  > *"Meet Kabir on Day 1. Kabir is greeted by verified trust badges, reading receipts, and an actionable 30-day onboarding roadmap linked directly to verified claims."*

---

### Shot 8: Grounded Handover Copilot & Deterministic Refusal (2:30 – 2:45)
- **Persona:** Kabir Sharma (Successor)
- **URL:** `/handovers/:id/portal` (Copilot Drawer)
- **Action:**
  1. Ask: *"What is blocking vendor sandbox access?"* $\rightarrow$ Copilot answers with citation `[PAY-142]`.
  2. Ask: *"How do we configure the Istio mesh?"* $\rightarrow$ Copilot responds with deterministic refusal:
     `"I can't verify this from the handover evidence. Here's what is missing: ..."`
- **Spoken Audio:**
  > *"The Handover Copilot answers grounded questions with exact artifact citations. But when asked about undocumented systems, it deterministically refuses to hallucinate."*

---

### Shot 9: Multi-Role Firewall & Cryptographic Governance (2:45 – 3:00)
- **Persona:** Dev (Contractor) $\rightarrow$ Sana (Auditor)
- **URL:** `/handovers/:id/portal` and `/governance`
- **Visual:**
  - **Dev's View:** Confidential vendor escalation contact is rendered as masked placeholder: `[Restricted: requires clearance 2]`.
  - **Sana's View:** Click **Verify Chain** $\rightarrow$ rolling SHA-256 audit log verified with zero breaks.
- **Spoken Audio:**
  > *"Our pre-retrieval SQL firewall guarantees that external contractors see zero confidential tokens. And for compliance, our auditor verifies our tamper-evident SHA-256 audit chain. RelayOps turns undocumented turnover into an immutable chain of truth."*

---

## Screenshot Export Checklist

For submission slide decks and documentation portals, export high-resolution (1920x1080) PNGs of the following screens:

| Frame # | Name | Route | Key Elements to Capture |
|:---:|---|---|---|
| **01** | `01_login_personas.png` | `/login` | 5 demo persona cards with role badges and clearance indicators |
| **02** | `02_redaction_transparency.png` | `/projects/payflow` | Redaction rules table, counts of scrubbed credentials, reassurance banner |
| **03** | `03_pipeline_stages.png` | `/handovers/:id/pipeline` | Real-time SSE stage cards with progress indicators |
| **04** | `04_decision_timeline.png` | `/handovers/:id/timeline` | Struck-through superseded decisions and red dashed conflict links |
| **05** | `05_dependency_topology.png` | `/handovers/:id/topology` | React Flow module graph with bus factor 1 risk badge |
| **06** | `06_review_studio_diff.png` | `/handovers/:id/review` | 3-pane split screen, open citation drawer, LCS word-level diff |
| **07** | `07_dual_signoff_modal.png` | `/handovers/:id/review` | Dual signature cards with SHA-256 version hash |
| **08** | `08_successor_portal.png` | `/handovers/:id/portal` | Trust strip, section acknowledgement receipt, readiness ring |
| **09** | `09_day1_30_board.png` | `/handovers/:id/portal` | 3 Kanban columns with priority badges and linked claim chips |
| **10** | `10_copilot_refusal.png` | `/handovers/:id/portal` | Grounded answer with `[PAY-142]` pill alongside deterministic refusal card |
| **11** | `11_contractor_firewall.png` | `/handovers/:id/portal` | `[Restricted: requires clearance 2]` masked placeholder cards |
| **12** | `12_audit_chain_verify.png` | `/governance` | Cryptographic audit log table with green "Chain Verified" banner |
