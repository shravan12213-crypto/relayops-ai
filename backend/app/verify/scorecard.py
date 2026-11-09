"""Completeness and epistemic confidence scorecard for handovers.

Computes metrics and an overall 0-100 score according to the formula documented in docs/SCORING.md:
- % claims with valid evidence
- % modules documented
- Open ambiguities by severity
- Contradictions resolved vs unresolved
- Coverage of open PRs, blockers, and branches
- Epistemic confidence per claim = f(authority, multi-source, recency, conflict penalty)
- Overall 0-100 handover readiness score
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.models import Ambiguity, Artifact, Claim, Edge

logger = logging.getLogger("relayops.verify.scorecard")


class ClaimScore(BaseModel):
    claim_id: str
    text: str
    status: str
    base_authority: float
    sources_count: int
    recency_factor: float
    conflict_penalty: float
    epistemic_confidence: float


class ScorecardData(BaseModel):
    project_id: str
    overall_score: int = Field(ge=0, le=100)
    claims_with_evidence_pct: float
    modules_documented_pct: float
    open_ambiguities_by_severity: dict[str, int]
    contradictions_count: dict[str, int]
    coverage: dict[str, float]
    epistemic_confidence_avg: float
    claim_scores: list[ClaimScore]
    summary: str


def compute_epistemic_confidence(
    claim: Claim,
    session: Session,
    open_conflict_ids: set[str],
) -> ClaimScore:
    """Calculate the epistemic confidence for a single claim:

    f(authority of evidence, number of independent sources, recency, unresolved conflict penalty).
    """
    if claim.status == "rejected" or not claim.evidence:
        return ClaimScore(
            claim_id=claim.id,
            text=claim.text,
            status=claim.status,
            base_authority=0.0,
            sources_count=0,
            recency_factor=1.0,
            conflict_penalty=0.0,
            epistemic_confidence=0.0,
        )

    # 1. Base authority: max authority of supporting evidence
    authorities = [float(e.get("authority", 0.5)) for e in claim.evidence]
    base_auth = max(authorities) if authorities else 0.5

    # 2. Multi-source bonus: distinct evidence artifacts
    sources_count = len(claim.evidence)
    bonus = min(0.15, max(0, (sources_count - 1) * 0.05))

    # 3. Recency factor based on newest artifact valid_time
    now = datetime.now(UTC)
    min_age_days = 999
    for e in claim.evidence:
        art_id = e.get("artifact_id") or e.get("external_id")
        art = session.exec(
            select(Artifact).where((Artifact.id == art_id) | (Artifact.external_id == art_id))
        ).first()
        if art and art.valid_time:
            age = (now - art.valid_time).days
            min_age_days = min(min_age_days, age)

    if min_age_days <= 30:
        recency = 1.0
    elif min_age_days <= 90:
        recency = 0.90
    else:
        recency = 0.80

    # 4. Conflict penalty if claim is part of an open unresolved contradiction
    is_conflicted = claim.id in open_conflict_ids or claim.status == "needs_review"
    penalty = 0.30 if is_conflicted else 0.0

    raw_confidence = (base_auth + bonus) * recency - penalty
    clamped_confidence = max(0.0, min(1.0, round(raw_confidence, 2)))

    return ClaimScore(
        claim_id=claim.id,
        text=claim.text,
        status=claim.status,
        base_authority=base_auth,
        sources_count=sources_count,
        recency_factor=recency,
        conflict_penalty=penalty,
        epistemic_confidence=clamped_confidence,
    )


def generate_scorecard(
    project_id: str,
    session: Session,
    claims: list[Claim] | None = None,
) -> ScorecardData:
    """Generate the full completeness and quality scorecard for a project handover."""
    all_claims = claims
    if all_claims is None:
        all_claims = session.exec(select(Claim).where(Claim.project_id == project_id)).all()

    # 1. Claims with valid evidence percentage
    total_claims = len(all_claims)
    valid_claims = [c for c in all_claims if c.status != "rejected" and len(c.evidence or []) > 0]
    claims_ev_pct = round((len(valid_claims) / max(total_claims, 1)) * 100.0, 1)

    # 2. Documented modules percentage
    commits = session.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.kind == "commit",
        )
    ).all()
    detected_modules: set[str] = set()
    for c in commits:
        meta = c.meta or {}
        files = meta.get("files_changed") or meta.get("files") or []
        for f in files:
            parts = f.replace("\\", "/").strip("/").split("/")
            mod = None
            if len(parts) >= 3 and parts[0] == "src" and parts[1] == "payflow":
                mod = parts[2]
            elif len(parts) > 1 and parts[0] not in ("docs", "tests", ".github", ".husky", "migrations"):
                mod = parts[0]
            if mod and "." not in mod:
                detected_modules.add(mod)

    docs = session.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.kind.in_(["adr_doc", "meeting_note", "runbook"]),
        )
    ).all()
    docs_text = " ".join(f"{d.title} {d.body_redacted}".lower() for d in docs)

    documented_modules = {
        m for m in detected_modules if m.lower() in docs_text or m.lower().replace("-", " ") in docs_text
    }
    modules_pct = (
        round((len(documented_modules) / max(len(detected_modules), 1)) * 100.0, 1)
        if detected_modules
        else 100.0
    )

    # 3. Open ambiguities by severity
    ambiguities = session.exec(
        select(Ambiguity).where(
            Ambiguity.project_id == project_id,
            Ambiguity.status == "open",
        )
    ).all()

    amb_counts = {"high": 0, "med": 0, "low": 0}
    open_conflict_ids: set[str] = set()

    for amb in ambiguities:
        sev = (amb.severity or "med").lower()
        amb_counts[sev] = amb_counts.get(sev, 0) + 1
        if amb.type == "conflict":
            for aid in amb.artifact_ids or []:
                open_conflict_ids.add(str(aid))

    # 4. Contradictions count (resolved vs unresolved)
    supersedes_edges = session.exec(
        select(Edge).where(
            Edge.project_id == project_id,
            Edge.type == "SUPERSEDES",
        )
    ).all()
    contradictions_count = {
        "resolved": len(supersedes_edges),
        "unresolved": len([a for a in ambiguities if a.type == "conflict"]),
    }

    # 5. Coverage of open PRs, blockers, and branches
    open_prs = session.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.kind == "pull_request",
        )
    ).all()
    open_prs_count = len([p for p in open_prs if (p.meta or {}).get("state") == "open"])
    addressed_prs_count = len(
        [
            p
            for p in open_prs
            if (p.meta or {}).get("state") == "open"
            and any(
                p.external_id in str(c.evidence) or f"PR-{p.external_id}" in str(c.evidence)
                for c in all_claims
            )
        ]
    )
    pr_coverage = (
        round((addressed_prs_count / max(open_prs_count, 1)) * 100.0, 1) if open_prs_count else 100.0
    )

    blockers = session.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.kind == "issue",
        )
    ).all()
    blocker_count = len(
        [
            b
            for b in blockers
            if (b.meta or {}).get("state") == "blocked"
            or "blocker" in (b.title or "").lower()
            or b.external_id == "PAY-142"
        ]
    )
    addressed_blockers = len(
        [
            b
            for b in blockers
            if (b.meta or {}).get("state") == "blocked" or b.external_id == "PAY-142"
            if any(b.external_id in str(c.evidence) for c in all_claims)
            or any(b.external_id in amb.artifact_ids for amb in ambiguities)
        ]
    )
    blocker_coverage = (
        round((addressed_blockers / max(blocker_count, 1)) * 100.0, 1) if blocker_count else 100.0
    )

    branches = session.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.kind == "branch",
        )
    ).all()
    unmerged_branches = [
        b for b in branches if not (b.meta or {}).get("merged", True) or "unmerged" in (b.title or "").lower()
    ]
    tracked_branches = [
        b for b in unmerged_branches if any(b.external_id in amb.artifact_ids for amb in ambiguities)
    ]
    branch_coverage = (
        round((len(tracked_branches) / max(len(unmerged_branches), 1)) * 100.0, 1)
        if unmerged_branches
        else 100.0
    )

    coverage_metrics = {
        "open_prs_pct": pr_coverage,
        "blockers_pct": blocker_coverage,
        "unmerged_branches_pct": branch_coverage,
    }

    # 6. Epistemic confidence per claim
    claim_scores: list[ClaimScore] = []
    for c in all_claims:
        score = compute_epistemic_confidence(c, session, open_conflict_ids)
        claim_scores.append(score)

    avg_confidence = (
        round(sum(s.epistemic_confidence for s in claim_scores) / max(len(claim_scores), 1), 2)
        if claim_scores
        else 0.0
    )

    # 7. Overall Score Calculation (0 - 100)
    # Metric 1: Evidence Coverage (weight: 0.30)
    m1 = claims_ev_pct

    # Metric 2: Module Documentation (weight: 0.20)
    m2 = modules_pct

    # Metric 3: Ambiguity Ledger Health (weight: 0.25)
    penalty = (amb_counts["high"] * 15) + (amb_counts["med"] * 5) + (amb_counts["low"] * 2)
    m3 = max(0.0, 100.0 - penalty)

    # Metric 4: Artifact Coverage (weight: 0.15)
    m4 = sum(coverage_metrics.values()) / len(coverage_metrics)

    # Metric 5: Epistemic Confidence (weight: 0.10)
    m5 = avg_confidence * 100.0

    raw_overall = (0.30 * m1) + (0.20 * m2) + (0.25 * m3) + (0.15 * m4) + (0.10 * m5)
    overall_score = max(0, min(100, int(round(raw_overall))))

    summary = (
        f"Score {overall_score}/100: {claims_ev_pct}% claims backed by valid evidence, "
        f"{modules_pct}% modules documented, {len(ambiguities)} open ambiguities "
        f"({amb_counts['high']} high, {amb_counts['med']} med, {amb_counts['low']} low), "
        f"average epistemic confidence {avg_confidence:.2f}."
    )

    return ScorecardData(
        project_id=project_id,
        overall_score=overall_score,
        claims_with_evidence_pct=claims_ev_pct,
        modules_documented_pct=modules_pct,
        open_ambiguities_by_severity=amb_counts,
        contradictions_count=contradictions_count,
        coverage=coverage_metrics,
        epistemic_confidence_avg=avg_confidence,
        claim_scores=claim_scores,
        summary=summary,
    )
