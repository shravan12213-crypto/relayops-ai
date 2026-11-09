# RelayOps Completeness & Readiness Scoring Specification

RelayOps computes an objective, deterministic 0–100 completeness score for project handovers.
Unlike unstructured LLM evaluations, this formula is transparent, mathematically reproducible,
and grounded directly in verified artifacts, source authority, and the Ambiguity Ledger.

---

## 1. Mathematical Formula

The overall score $S \in [0, 100]$ is a weighted linear combination of five quality pillars:

$$
S = \operatorname{round}\Big(0.30 \cdot M_1 + 0.20 \cdot M_2 + 0.25 \cdot M_3 + 0.15 \cdot M_4 + 0.10 \cdot M_5\Big)
$$

| Pillar | Metric Name | Weight | Definition & Rationale |
|---|---|:---:|---|
| $M_1$ | **Evidence Coverage** | 30% | Percentage of handover claims with $\ge 1$ verified artifact link (substring match and deep link). Claims with zero valid evidence are rejected and penalize this metric. |
| $M_2$ | **Module Documentation** | 20% | Percentage of codebase modules (top-level packages with $\ge 3$ commits) with corresponding ADR, meeting note, or runbook references. |
| $M_3$ | **Ambiguity Ledger Health** | 25% | Penalty-based score derived from open ambiguities: $\max(0, 100 - (15 \times \text{High} + 5 \times \text{Med} + 2 \times \text{Low}))$. High severity includes unclosed threads, undocumented modules, orphan branches, and open contradictions. |
| $M_4$ | **Artifact Coverage** | 15% | Mean coverage across active unmerged branches, open pull requests, and blocker tickets addressed either by verified claims or tracked in the Ambiguity Ledger. |
| $M_5$ | **Epistemic Confidence** | 10% | Scaled mean epistemic confidence ($\bar{C} \times 100$) across all accepted claims. |

---

## 2. Epistemic Confidence per Claim

For each claim $c$, epistemic confidence $C(c) \in [0.0, 1.0]$ evaluates the evidentiary authority, diversity of sources, temporal recency, and contradiction state:

$$
C(c) = \operatorname{clamp}\Big(0.0, 1.0, (A + S) \times R - P\Big)
$$

### Parameters:
1. **Base Source Authority ($A \in [0.0, 1.0]$)**:
   - `1.0`: Merged Pull Request, Production Code File
   - `0.8`: Jira / GitHub Issue Ticket
   - `0.6`: Architecture Decision Record (ADR), Meeting Note, Runbook
   - `0.5`: Unmerged Branch, Closed/Unmerged PR
   - `0.4`: Informal Chat Thread (Slack)
   - `0.0`: Rejected claim or claim lacking evidence

2. **Independent Sources Bonus ($S \in [0.0, 0.15]$)**:
   - Multi-source corroboration adds $+0.05$ per additional distinct artifact (capped at $+0.15$).

3. **Recency Multiplier ($R \in [0.8, 1.0]$)**:
   - Age $\le 30$ days: $R = 1.0$
   - Age $31 - 90$ days: $R = 0.90$
   - Age $> 90$ days: $R = 0.80$

4. **Contradiction Penalty ($P \in \{0.0, 0.30\}$)**:
   - If the claim is flagged with an open contradiction in the Ambiguity Ledger or marked `needs_review`, a flat $-0.30$ penalty is applied.

---

## 3. Ambiguity Severity Classification

| Ambiguity Type | Default Severity | Description |
|---|:---:|---|
| `orphan_branch` | **High** | Unmerged branch with active development commits. |
| `conflict` | **High** | Contemporaneous contradiction between equal-authority sources with no code resolution. |
| `undocumented_module` | **High** | Active module with $\ge 3$ commits and zero documentation (bus factor 1 risk). |
| `missing_doc` | **High** | Open blocker ticket with no associated operational runbook. |
| `unclosed_thread` | **High** | Question addressed to outgoing engineer with no reply. |
| `stale_config` | **Medium** | Config variable ending in `_OLD` / `_DEPRECATED` referenced in fallback routines. |
| `low_evidence` | **Low** | Accepted claim supported solely by chat messages (authority $\le 0.4$). |
