# RelayOps Access Control & Governance Policy Specification

RelayOps enforces an Attribute-Based Access Control (ABAC) security model implemented via pure Python policy functions in `backend/app/policy.py`. Access decisions are verified at the HTTP boundary, injected directly into SQL queries before retrieval, and validated at every state transition.

---

## 1. Sensitivity Classification

All project artifacts, extracted claims, and discussions are categorized into 4 strict sensitivity levels:

| Level | Classification | Description | Typical Source Examples |
|:---:|---|---|---|
| **0** | **Public** | Publicly shareable documentation or open-source repositories | Public READMEs, open GitHub issue discussions, public release notes |
| **1** | **Internal** | Default team communications and active technical work | Pull requests, general `#backend-dev` Slack chatter, architecture decisions, Jira stories |
| **2** | **Confidential** | Sensitive organizational, commercial, or personnel data | Vendor escalation contacts, private contract discussions, HR compensation channels |
| **3** | **Restricted** | Critical executive decisions, active security exploits, legal agreements | Master API credentials, legal disclosures, board-level handover notes |

Every authenticated user is assigned a clearance level from `0` to `3`. The fundamental access rule states:

$$\text{can\_view}(user, resource) \iff \text{effective\_clearance}(user) \ge \text{sensitivity}(resource)$$

---

## 2. Roles and Clearance Caps

RelayOps defines 5 distinct organizational personas, each designed with specific clearance caps and permission boundaries:

| Persona | Role Identifier | Clearance Cap | Visibility Constraints | Permitted Actions |
|---|:---:|:---:|---|---|
| **Team Lead** | `lead` | Level 3 (Uncapped) | Full visibility across all clearance levels within project | Sign off, Deliver, Waive ambiguities, View audit logs, Edit claims, Manage members |
| **Outgoing Engineer** | `outgoing` | Level 2-3 (Uncapped) | Full visibility over own contributions and project history | Edit claims, Resolve ambiguities, Create version snapshots, Sign off |
| **Successor** | `successor` | Level 1 (Default) | Sees verified handover claims up to clearance level | Acknowledge section receipts, Update Day 1-30 plan status, Query Copilot |
| **External Contractor** | `contractor` | **Strictly capped at 1** | Confidential & Restricted items masked; no access to raw secrets | Query Copilot within permitted scope, view non-confidential claims |
| **Compliance Auditor** | `auditor` | **Strictly capped at 1** | **Metadata, scorecards, and audit logs only**; raw artifact bodies forbidden | View audit logs, Verify cryptographic chain, Inspect readiness scorecards |

### Effective Clearance Calculation
```python
def effective_clearance(user: Any, handover: Any = None) -> int:
    role = user.role.lower()
    base_clearance = user.clearance

    # Hard role caps enforced unconditionally
    if role in ("contractor", "auditor"):
        return min(base_clearance, 1)

    return base_clearance
```

---

## 3. Allowed Actions Matrix

The `allowed_actions(user, handover)` function computes permissible operations for each role:

| Action Identifier | Description | `lead` | `outgoing` | `successor` | `contractor` | `auditor` |
|---|---|:---:|:---:|:---:|:---:|:---:|
| `view_handover` | View delivered or in-progress handover | Yes | Yes | Yes | Yes | Yes |
| `edit_claims` | Edit claim text, accept, or reject | Yes | Yes | No | No | No |
| `create_claim` | Add a manual human-authored claim | Yes | Yes | No | No | No |
| `resolve_ambiguity` | Mark an ambiguity resolved with note | Yes | Yes | No | No | No |
| `waive_ambiguity` | Waive an ambiguity without resolution | Yes | No | No | No | No |
| `create_snapshot` | Freeze version snapshot with SHA-256 hash | Yes | Yes | No | No | No |
| `signoff` | Submit cryptographic HMAC sign-off | Yes | Yes | No | No | No |
| `deliver` | Mark handover delivered to successor | Yes | No | No | No | No |
| `acknowledge_receipt` | Submit section reading receipt & note | No | No | Yes | No | No |
| `update_plan_status` | Move Day 1-30 tasks (todo / doing / done) | Yes | Yes | Yes | No | No |
| `chat` | Query Grounded Handover Copilot | Yes | Yes | Yes | Yes | No |
| `view_audit_log` | Inspect cryptographic event logs | Yes | No | No | No | Yes |
| `verify_chain` | Validate rolling SHA-256 hash chain | Yes | No | No | No | Yes |
| `manage_members` | Invite members and adjust clearances | Yes | No | No | No | No |

---

## 4. Pre-Inference Permission Firewall

Unlike systems that mask sensitive information in LLM generated responses, RelayOps filters inputs **in SQL before retrieval and before LLM inference**:

```sql
SELECT a.id, a.title, a.body_redacted, a.sensitivity
FROM artifact_fts f
JOIN artifact a ON a.rowid = f.rowid
WHERE artifact_fts MATCH :query_expression
  AND a.project_id = :project_id
  AND a.sensitivity <= :effective_clearance
ORDER BY f.rank
LIMIT :limit;
```

### Security Invariants:
1. Low-clearance users (e.g., Contractors with clearance 1) will never cause Level 2 or 3 artifacts to be fetched from disk.
2. The LLM context prompt receives only permitted text tokens.
3. In the event of prompt injection attempts inside user queries, the LLM cannot leak confidential data because it lacks access to the tokens.

---

## 5. UI Claim Masking Behavior

When claims are rendered in the Successor Portal or Review Studio for users whose effective clearance is less than the claim's sensitivity:
- The `text` attribute is replaced with: `"Restricted: requires clearance {sensitivity}"`.
- The `evidence` array is purged: `[]`.
- `is_masked` is flagged as `True`.
- Citation pills render as locked gray badges: `[Locked: Clearance {N}]`.

---

## 6. Dual Sign-Off & Snapshot State Machine

A handover transitions through strict lifecycle states:

```
[draft] ---> [reconstructing] ---> [in_review] ---> [signed] ---> [delivered]
```

1. **`in_review`**: The outgoing contributor and lead review extracted claims, resolve contradictions, and address open ambiguities.
2. **Snapshot Creation**: Freezes an immutable `HandoverVersion` record containing the full JSON payload of all accepted claims, resolved ambiguities, and the SHA-256 hash of the previous version.
3. **Dual Signature Requirement**:
   - Outgoing contributor signs snapshot $V_N$ using an HMAC signature. Handover status remains `in_review`.
   - Team Lead inspects snapshot $V_N$ and signs. Once **both** signatures match the exact same version hash, status transitions to `signed`.
4. **Delivery**: The team lead executes the final delivery step, transitioning status to `delivered`.
5. **Edit Invalidation**: If any claim is edited after sign-off, existing signatures are invalidated, and a new snapshot $V_{N+1}$ must be created and signed by both parties.

---

## 7. Section Comprehension Receipts

To verify onboarding accountability, successors acknowledge reading each section of the delivered handover:
- **Receipt Record**: Captures `handover_id`, `user_id`, `section`, `acknowledged_at` (UTC timestamp), and an optional `comprehension_note`.
- **Readiness Tracking**: The Successor Portal computes an overall acknowledgement progress percentage.
- **Audit Logging**: Every receipt submission is cryptographically logged in the tamper-evident audit log.
