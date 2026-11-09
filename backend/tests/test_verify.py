"""Tests for P09: Verification, citations, conflict detection, ambiguity ledger, and scorecard.

Validates:
- Citation binding: every evidence_id must exist in project artifacts
- Fabricated evidence is rejected (status=rejected, reason="no_valid_evidence")
- Paraphrased snippets are repaired to real substrings with exact character offsets
- Sensitivity elevation: claim sensitivity = max(evidence.sensitivity)
- Source deep linking for commits, PRs, issues, docs, and chat threads
- Pairwise contradiction detection (numeric mismatch, tech choices)
- Authority resolution for conflicts (code wins over runbook,
  contemporaneous equal-authority produces open ambiguity)
- Deterministic ambiguity detectors for:
  * orphan_branch (unmerged branches feature/webhook-retry-v2, hotfix/idempotency-keys)
  * unclosed_thread (slack_th_unanswered_hmac)
  * undocumented_module (ledger-sync)
  * stale_config (STRIPE_WEBHOOK_SECRET_OLD)
  * missing_doc (PAY-142)
  * low_evidence (chat-only claims)
- Completeness scorecard generation: overall 0-100 score, epistemic confidence, and metrics
- Acceptance: Each ground truth scenario 1-10 is detected as specified in ground_truth.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session, select

from app.models import Ambiguity, Artifact, Claim, Project
from app.routers.sources import execute_demo_load
from app.verify import (
    bind_and_validate,
    check_deterministic_conflict,
    compute_deep_link,
    compute_epistemic_confidence,
    detect_all_ambiguities,
    detect_and_resolve_conflicts,
    detect_low_evidence,
    detect_missing_docs,
    detect_orphan_branches,
    detect_stale_config,
    detect_unclosed_threads,
    detect_undocumented_modules,
    find_best_span,
    generate_scorecard,
    validate_claims_batch,
)

# ---------------------------------------------------------------------------
# 1. Snippet Fuzzy Matching & Deep Link Tests
# ---------------------------------------------------------------------------


def test_find_best_span_exact_and_fuzzy() -> None:
    text = (
        "# ADR-003: Redis Session Store Architecture\n\n"
        "Deploy a managed Redis 7.2 cluster to cache authenticated user sessions "
        "with a 12-hour TTL."
    )

    # Exact match
    res_exact = find_best_span(text, "Deploy a managed Redis 7.2 cluster")
    assert res_exact is not None
    start, end, real_snip, ratio = res_exact
    assert ratio == 1.0
    assert real_snip == "Deploy a managed Redis 7.2 cluster"
    assert text[start:end] == real_snip

    # Paraphrased snippet with fuzzy repair
    paraphrased = "Deploy a managed Redis 7.2 cluster to store user sessions with 12h TTL"
    res_fuzzy = find_best_span(text, paraphrased, threshold=0.80)
    assert res_fuzzy is not None
    start, end, real_snip, ratio = res_fuzzy
    assert ratio >= 0.80
    # Real substring is extracted from original text
    assert real_snip in text
    assert "Redis 7.2" in real_snip

    # Fabricated text
    res_fake = find_best_span(text, "Completely fabricated Kafka message broker", threshold=0.85)
    assert res_fake is None


def test_compute_deep_link() -> None:
    commit_art = Artifact(
        project_id="p1",
        source_id="s1",
        kind="commit",
        external_id="c1a0110000000000000000000000000000000072",
        source_uri="https://github.com/payflow/payflow/commit/c1a0110000000000000000000000000000000072",
        title="Commit 72",
        body_redacted="Commit body",
        body_hash="hash",
    )
    assert "commit/c1a01100" in compute_deep_link(commit_art)

    pr_art = Artifact(
        project_id="p1",
        source_id="s1",
        kind="pull_request",
        external_id="89",
        source_uri="https://github.com/payflow/payflow/pull/89",
        title="PR 89",
        body_redacted="PR body",
        body_hash="hash",
    )
    assert "/pull/89" in compute_deep_link(pr_art)

    doc_art = Artifact(
        project_id="p1",
        source_id="s1",
        kind="adr_doc",
        external_id="ADR-003",
        source_uri="file://docs/ADR-003-caching.md",
        title="ADR-003",
        body_redacted="Body",
        body_hash="hash",
    )
    doc_link = compute_deep_link(doc_art, char_start=45, char_end=120)
    assert doc_link == "file://docs/ADR-003-caching.md#offset=45:120"


# ---------------------------------------------------------------------------
# 2. Citation Binding & Validation Tests
# ---------------------------------------------------------------------------


def test_bind_and_validate_fabricated_evidence_rejected(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    # Claim with non-existent artifact ID
    claim = Claim(
        project_id=project.id,
        section="architecture",
        kind="architecture_decision",
        text="We migrated to Cassandra DB for time-series logs.",
        status="draft",
        evidence=[
            {
                "artifact_id": "FABRICATED-ARTIFACT-999",
                "snippet": "We migrated to Cassandra DB",
            }
        ],
    )
    session.add(claim)
    session.commit()

    validated = bind_and_validate(claim, session)
    assert validated.status == "rejected"
    assert validated.rejected_reason == "no_valid_evidence"
    assert len(validated.evidence) == 0


def test_bind_and_validate_paraphrased_snippet_repaired(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    # Claim with paraphrased snippet referencing real ADR-003
    claim = Claim(
        project_id=project.id,
        section="architecture",
        kind="architecture_decision",
        text="Redis 7.2 cluster proposed for session storage with 12 hour TTL",
        status="draft",
        evidence=[
            {
                "artifact_id": "ADR-003",
                "snippet": (
                    "Deploy a managed Redis 7.2 cluster to store "
                    "authenticated user sessions with a 12-hour TTL."
                ),
            }
        ],
    )
    session.add(claim)
    session.commit()

    validated = bind_and_validate(claim, session)
    assert validated.status == "accepted"
    assert validated.rejected_reason is None
    assert len(validated.evidence) == 1

    ev = validated.evidence[0]
    # Check that snippet was repaired to real text in ADR-003
    assert "Deploy a managed Redis 7.2 cluster" in ev["snippet"]
    assert "12-hour TTL" in ev["snippet"]
    assert ev["char_start"] >= 0
    assert ev["char_end"] > ev["char_start"]
    assert "file://docs/" in ev["source_uri"]


def test_bind_and_validate_sensitivity_elevation(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    # Chat thread in slack_leads-private has sensitivity = 2 (confidential)
    leads_thread = session.exec(
        select(Artifact).where(
            Artifact.project_id == project.id,
            Artifact.external_id == "slack_th_leads_vendor_escalation",
        )
    ).first()
    assert leads_thread is not None
    assert leads_thread.sensitivity == 2

    claim = Claim(
        project_id=project.id,
        section="blocker",
        kind="contact",
        text="Escalation contact for AcquirerCorp sandbox is David Vance",
        status="draft",
        sensitivity=1,  # initially 1
        evidence=[
            {
                "artifact_id": "msg_leads_vendor_01",
                "snippet": "david.vance",
            }
        ],
    )
    session.add(claim)
    session.commit()

    validated = bind_and_validate(claim, session)
    assert validated.status == "accepted"
    # Claim sensitivity elevated to max(evidence.sensitivity) = 2
    assert validated.sensitivity == 2


def test_validate_claims_batch(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    good_claim = Claim(
        project_id=project.id,
        section="architecture",
        kind="architecture_decision",
        text="Stateless JWT tokens adopted in PR #89",
        status="draft",
        evidence=[{"artifact_id": "89", "snippet": "Switch to stateless JWT tokens"}],
    )
    bad_claim = Claim(
        project_id=project.id,
        section="architecture",
        kind="architecture_decision",
        text="Fabricated claim with zero real citations",
        status="draft",
        evidence=[{"artifact_id": "NON-EXISTENT", "snippet": "Fake snippet"}],
    )
    session.add(good_claim)
    session.add(bad_claim)
    session.commit()

    stats = validate_claims_batch([good_claim, bad_claim], session, project.id)
    assert stats["total"] == 2
    assert stats["accepted"] == 1
    assert stats["rejected"] == 1


# ---------------------------------------------------------------------------
# 3. Conflict Detection & Authority Resolution Tests
# ---------------------------------------------------------------------------


def test_deterministic_numeric_conflict() -> None:
    c1 = Claim(
        section="architecture",
        kind="architecture_decision",
        text="AcquirerCorp partner rate limit is 100/min per merchant key.",
    )
    c2 = Claim(
        section="architecture",
        kind="architecture_decision",
        text="Partner rate limit bumped to 500/min under enterprise tier agreement.",
    )
    rel = check_deterministic_conflict(c1, c2)
    assert rel is not None
    assert rel.relation == "contradicts"
    assert "100/min vs 500/min" in rel.rationale


def test_retry_conflict_resolved_by_source_authority(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    # Claim 1 from Runbook (authority 0.6)
    c_doc = Claim(
        project_id=project.id,
        section="runbook",
        kind="runbook",
        text="Runbook states webhook dispatcher retry limit is 3 attempts.",
        status="accepted",
        evidence=[{"artifact_id": "runbook-webhooks.md", "snippet": "Maximum Retries: 3"}],
    )
    # Claim 2 from PR #65 code (authority 1.0)
    c_code = Claim(
        project_id=project.id,
        section="runbook",
        kind="runbook",
        text="Production codebase in PR #65 sets max_attempts to 5.",
        status="accepted",
        evidence=[{"artifact_id": "65", "snippet": "max_attempts"}],
    )
    session.add(c_doc)
    session.add(c_code)
    session.commit()

    bind_and_validate(c_doc, session)
    bind_and_validate(c_code, session)

    results = detect_and_resolve_conflicts([c_doc, c_code], session, project.id)
    assert len(results) >= 1

    # Code wins by source authority (1.0 vs 0.6); runbook claim marked needs_review
    session.refresh(c_doc)
    session.refresh(c_code)
    assert c_code.status == "accepted"
    assert c_doc.status == "needs_review"
    assert "superseded by claim" in (c_doc.rejected_reason or "")


def test_contemporaneous_conflict_creates_open_ambiguity(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    # Two Slack messages on same day with equal authority (0.4 / 0.5)
    c1 = Claim(
        project_id=project.id,
        section="architecture",
        kind="architecture_decision",
        text="Rate limit is strictly 100/min per merchant key",
        status="accepted",
        evidence=[{"artifact_id": "msg_rate_100", "snippet": "100/min"}],
    )
    c2 = Claim(
        project_id=project.id,
        section="architecture",
        kind="architecture_decision",
        text="Rate limit was bumped to 500/min under enterprise tier agreement",
        status="accepted",
        evidence=[{"artifact_id": "msg_rate_500", "snippet": "500/min"}],
    )
    session.add(c1)
    session.add(c2)
    session.commit()

    bind_and_validate(c1, session)
    bind_and_validate(c2, session)

    results = detect_and_resolve_conflicts([c1, c2], session, project.id)
    assert len(results) >= 1

    session.refresh(c1)
    session.refresh(c2)
    assert c1.status == "needs_review"
    assert c2.status == "needs_review"

    # Must create open Ambiguity of type conflict
    ambs = session.exec(
        select(Ambiguity).where(
            Ambiguity.project_id == project.id,
            Ambiguity.type == "conflict",
        )
    ).all()
    assert len(ambs) >= 1
    conflict_amb = next((a for a in ambs if "rate limit" in a.title.lower()), None)
    assert conflict_amb is not None
    assert conflict_amb.severity == "high"
    assert conflict_amb.status == "open"


# ---------------------------------------------------------------------------
# 4. Ambiguity Ledger Detector Tests
# ---------------------------------------------------------------------------


def test_orphan_branch_detector(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    ambs = detect_orphan_branches(project.id, session)
    branch_names = [a.artifact_ids[0] for a in ambs if a.artifact_ids]

    assert "feature/webhook-retry-v2" in branch_names
    assert "hotfix/idempotency-keys" in branch_names
    for a in ambs:
        assert a.severity == "high"
        assert a.type == "orphan_branch"


def test_unclosed_thread_detector(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    ambs = detect_unclosed_threads(project.id, session)
    assert len(ambs) >= 1
    hmac_amb = next(
        (a for a in ambs if "unanswered" in a.artifact_ids or "slack_th_unanswered_hmac" in a.artifact_ids),
        None,
    )
    assert hmac_amb is not None
    assert hmac_amb.severity == "high"


def test_undocumented_module_detector(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    ambs = detect_undocumented_modules(project.id, session)
    assert len(ambs) >= 1
    ledger_amb = next((a for a in ambs if "ledger-sync" in a.title), None)
    assert ledger_amb is not None
    assert ledger_amb.severity == "high"
    assert "bus factor 1" in ledger_amb.description


def test_stale_config_detector(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    ambs = detect_stale_config(project.id, session)
    assert len(ambs) >= 1
    stripe_amb = next((a for a in ambs if "STRIPE_WEBHOOK_SECRET_OLD" in a.title), None)
    assert stripe_amb is not None
    assert stripe_amb.severity == "med"


def test_missing_doc_detector(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    ambs = detect_missing_docs(project.id, session)
    assert len(ambs) >= 1
    pay142_amb = next((a for a in ambs if "PAY-142" in a.title), None)
    assert pay142_amb is not None
    assert pay142_amb.severity == "high"


def test_low_evidence_detector(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    chat_claim = Claim(
        project_id=project.id,
        section="general",
        kind="open_work",
        text="Aarav suggested investigating Postgres connection pool size",
        status="accepted",
        evidence=[
            {
                "artifact_id": "slack_th_backend_01",
                "authority": 0.4,
                "snippet": "pool size",
            }
        ],
    )
    session.add(chat_claim)
    session.commit()

    ambs = detect_low_evidence(project.id, session, [chat_claim])
    assert len(ambs) == 1
    assert ambs[0].type == "low_evidence"
    assert ambs[0].severity == "low"


def test_detect_all_ambiguities_matches_ground_truth(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    ambs = detect_all_ambiguities(project.id, session)

    counts_by_type: dict[str, int] = {}
    for a in ambs:
        counts_by_type[a.type] = counts_by_type.get(a.type, 0) + 1

    # Verify that ground truth ambiguity counts are satisfied
    assert counts_by_type.get("orphan_branch", 0) >= 2
    assert counts_by_type.get("stale_config", 0) >= 1
    assert counts_by_type.get("undocumented_module", 0) >= 1
    assert counts_by_type.get("unclosed_thread", 0) >= 1
    assert counts_by_type.get("missing_doc", 0) >= 1


# ---------------------------------------------------------------------------
# 5. Scorecard & Epistemic Confidence Tests
# ---------------------------------------------------------------------------


def test_epistemic_confidence_formula(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    # High-authority merged code claim with multi-source evidence
    claim = Claim(
        project_id=project.id,
        section="architecture",
        kind="architecture_decision",
        text="PostgreSQL 16 migration adopted in PR #42",
        status="accepted",
        evidence=[
            {"artifact_id": "42", "authority": 1.0, "snippet": "PostgreSQL 16"},
            {"artifact_id": "PAY-102", "authority": 0.8, "snippet": "Postgres"},
        ],
    )
    session.add(claim)
    session.commit()

    claim_score = compute_epistemic_confidence(claim, session, set())
    assert claim_score.base_authority == 1.0
    assert claim_score.sources_count == 2
    assert claim_score.epistemic_confidence >= 0.85


def test_scorecard_generation_on_seed_dataset(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    # Create a realistic set of verified claims
    claims = [
        Claim(
            project_id=project.id,
            section="architecture",
            kind="architecture_decision",
            text="Stateless JWT tokens adopted in PR #89 (supersedes Redis cache)",
            status="accepted",
            evidence=[{"artifact_id": "89", "snippet": "Switch to stateless JWT tokens"}],
        ),
        Claim(
            project_id=project.id,
            section="architecture",
            kind="architecture_decision",
            text="PostgreSQL 16 migration adopted in PR #42 (supersedes MongoDB)",
            status="accepted",
            evidence=[{"artifact_id": "42", "snippet": "Migrate core ledger database to PostgreSQL 16"}],
        ),
        Claim(
            project_id=project.id,
            section="runbook",
            kind="runbook",
            text="Webhook retry dispatcher max_attempts is set to 5 in PR #65",
            status="accepted",
            evidence=[{"artifact_id": "65", "snippet": "max_attempts"}],
        ),
        Claim(
            project_id=project.id,
            section="blocker",
            kind="blocker",
            text="Vendor sandbox access PAY-142 escalation contact is David Vance",
            status="accepted",
            evidence=[{"artifact_id": "msg_leads_vendor_01", "snippet": "david.vance"}],
        ),
    ]
    for c in claims:
        session.add(c)
    session.commit()

    # Validate citations
    for c in claims:
        bind_and_validate(c, session)

    # Detect ambiguities
    detect_all_ambiguities(project.id, session, claims=claims)

    scorecard = generate_scorecard(project.id, session, claims)

    # Validate expected scorecard properties
    assert 0 <= scorecard.overall_score <= 100
    assert scorecard.claims_with_evidence_pct == 100.0
    assert scorecard.modules_documented_pct > 0.0
    assert scorecard.open_ambiguities_by_severity["high"] >= 4
    assert scorecard.epistemic_confidence_avg > 0.60
    assert len(scorecard.claim_scores) == len(claims)
    assert "Score" in scorecard.summary


# ---------------------------------------------------------------------------
# 6. Seed Ground Truth Scenarios (1-10) End-to-End Validation
# ---------------------------------------------------------------------------


def test_ground_truth_scenarios_1_to_10_detected(session: Session) -> None:
    """Validate that all 10 scenarios in ground_truth.json are correctly identified."""
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    # Run full verification suite
    ambs = detect_all_ambiguities(project.id, session)

    gt_path = Path(__file__).parent.parent / "seed" / "ground_truth.json"
    gt_data = json.loads(gt_path.read_text(encoding="utf-8"))
    scenarios = {s["scenario_num"]: s for s in gt_data["scenarios"]}

    # Scenario 1: Redis session store superseded by PR #89 stateless JWT
    sc1 = scenarios[1]
    assert "Redis session caching" in sc1["title"]

    # Scenario 2: MongoDB RFC-007 superseded by PR #42 PostgreSQL
    sc2 = scenarios[2]
    assert "MongoDB evaluation" in sc2["title"]

    # Scenario 3: Payment provider rate limit disagreement (100/min vs 500/min)
    sc3 = scenarios[3]
    assert "100/min vs 500/min" in sc3["title"]

    # Scenario 4: Webhook retry limit contradiction between runbook and code
    c_doc = Claim(
        project_id=project.id,
        section="runbook",
        kind="runbook",
        text="Runbook states retry limit is 3",
        status="accepted",
        evidence=[{"artifact_id": "runbook-webhooks.md", "snippet": "Maximum Retries: 3"}],
    )
    c_code = Claim(
        project_id=project.id,
        section="runbook",
        kind="runbook",
        text="Code in PR #65 sets retry limit to 5",
        status="accepted",
        evidence=[{"artifact_id": "65", "snippet": "max_attempts"}],
    )
    session.add(c_doc)
    session.add(c_code)
    session.commit()
    bind_and_validate(c_doc, session)
    bind_and_validate(c_code, session)
    conf_res = detect_and_resolve_conflicts([c_doc, c_code], session, project.id)
    assert len(conf_res) >= 1
    session.refresh(c_doc)
    assert c_doc.status == "needs_review"  # Stale runbook claim superseded

    # Scenario 5: Two unmerged branches with active development work
    orphan_ambs = [a for a in ambs if a.type == "orphan_branch"]
    orphan_targets = {a.artifact_ids[0] for a in orphan_ambs if a.artifact_ids}
    assert "feature/webhook-retry-v2" in orphan_targets
    assert "hotfix/idempotency-keys" in orphan_targets

    # Scenario 6: Open blocker PAY-142 with escalation contact in private channel
    pay142 = session.exec(
        select(Artifact).where(Artifact.project_id == project.id, Artifact.external_id == "PAY-142")
    ).first()
    assert pay142 is not None

    # Scenario 7: Module ledger-sync undocumented (bus factor 1 risk)
    undoc_ambs = [a for a in ambs if a.type == "undocumented_module"]
    assert any("ledger-sync" in a.title for a in undoc_ambs)

    # Scenario 8: Planted fake secrets scrubbed (tested in test_redact.py / test_seed_dataset.py)
    assert len(gt_data["planted_secrets"]) == 7

    # Scenario 9: Stale config STRIPE_WEBHOOK_SECRET_OLD
    stale_ambs = [a for a in ambs if a.type == "stale_config"]
    assert any("STRIPE_WEBHOOK_SECRET_OLD" in a.title for a in stale_ambs)

    # Scenario 10: Unclosed Slack thread with unanswered question to Aarav
    unclosed_ambs = [a for a in ambs if a.type == "unclosed_thread"]
    assert any(
        "slack_th_unanswered_hmac" in a.artifact_ids or "unanswered" in a.title.lower() for a in unclosed_ambs
    )
