# RelayOps ABAC Policy Specification

## 1. Sensitivity Levels
All artifacts and claims are classified into 4 strict sensitivity levels:

| Level | Name | Description | Example Content |
|---|---|---|---|
| **0** | **Public** | Open-source or public disclosures | Public GitHub issues, open README |
| **1** | **Internal** | Standard internal team communications | Pull requests, general Slack channels, architecture decisions |
| **2** | **Confidential** | Sensitive organizational & personnel data | Vendor contracts, pricing negotiations, private escalation threads |
| **3** | **Restricted** | Legal, executive, or critical security secrets | Security audits, credentials, legal agreements |

Users possess a clearance level from `0` to `3`. Access is denied whenever $\text{clearance} < \text{sensitivity}$.

---

## 2. Roles and Clearance Caps
Each user has a designated organizational role with explicit capabilities and clearance caps:

| Role | Default / Max Clearance | Visibility Constraints | Permitted Actions |
|---|:---:|---|---|
| **Lead** | 3 (Uncapped) | Full visibility across all clearance levels within project | Sign off, Deliver, Waive ambiguities, View audit logs, Edit claims |
| **Outgoing** | 2-3 (Uncapped) | Sees own project history and contributions | Edit claims, Resolve ambiguities, Sign off, Create snapshots |
| **Successor** | 1 (User's clearance) | Sees handovers and permitted evidence up to clearance | Acknowledge receipts, Update 30-day plan status, Ask Copilot |
| **Contractor** | **Capped at 1** | **Strictly capped at clearance $\le 1$**; all confidential content masked | Chat within permitted scope, view non-confidential claims |
| **Auditor** | **Capped at 1** | **Metadata and scorecard only**; raw artifact bodies are NEVER visible | View audit logs, Verify cryptographic chain, Inspect scorecards |

---

## 3. Pre-Inference Permission Firewall
Permission checks are enforced **in SQL before retrieval and before LLM inference**, not by redacting or filtering after generation:

```sql
SELECT a.id
FROM artifact_fts f
JOIN artifact a ON a.rowid = f.rowid
WHERE artifact_fts MATCH :match_expr
  AND a.project_id = :project_id
  AND a.sensitivity <= :effective_clearance
ORDER BY f.rank
LIMIT :limit
```

This guarantees that:
1. No sensitive tokens ever enter the LLM context prompt for low-clearance users.
2. Even in the event of prompt injection or model hallucination, restricted data cannot leak because the LLM never received it.

---

## 4. Claim Masking Behavior
When claims are rendered for users with insufficient clearance:
- The `text` field is replaced with: `"Restricted: requires clearance {N}"`.
- The `evidence` list is stripped to `[]`.
- `is_masked` is flagged as `True`.

---

## 5. Dual Sign-Off Rule
A handover cannot transition to `signed` or `delivered` without cryptographic sign-offs from **both** the Outgoing Contributor and the Team Lead on the **exact same version snapshot**.

