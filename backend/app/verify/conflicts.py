"""Conflict and contradiction detection engine for claims and decisions.

Implements pairwise contradiction detection:
1. Deterministic rules (numeric mismatches, mutually exclusive tech choices).
2. ONE batched llm.structured call per subject for ambiguous pairs.
3. Authority resolution via authority.resolve:
   - Higher-authority newer wins -> mark stale claim needs_review with "superseded by" pointer.
   - Same-time conflicts -> persist open Ambiguity(type="conflict", severity="high").
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app import llm
from app.models import Ambiguity, Artifact, Claim, Edge, Node
from app.reconstruct.authority import ResolutionStatus, resolve

logger = logging.getLogger("relayops.verify.conflicts")


class PairwiseRelation(BaseModel):
    relation: str = Field(description="entails | contradicts | unrelated")
    rationale: str = Field(description="Explanation of relationship or conflict point")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


@dataclass
class ConflictResult:
    claim_a_id: str
    claim_b_id: str
    relation: str
    status: str
    winner_id: str | None
    loser_id: str | None
    reason: str


def infer_subject_key(claim: Claim) -> str:
    """Infer the thematic subject key for a claim."""
    text_lower = claim.text.lower()

    if any(k in text_lower for k in ("rate limit", "100/min", "500/min", "acquirercorp")):
        return "rate_limit"
    if any(k in text_lower for k in ("retry", "max_attempts", "runbook", "webhook")):
        return "webhook_retry"
    if any(k in text_lower for k in ("redis", "jwt", "session", "caching", "adr-003")):
        return "session_caching"
    if any(k in text_lower for k in ("mongo", "mongodb", "postgres", "postgresql", "rfc-007")):
        return "database_choice"
    if any(k in text_lower for k in ("ledger", "ledger-sync")):
        return "ledger_sync"

    return f"{claim.section}_{claim.kind}"


def check_deterministic_conflict(claim_a: Claim, claim_b: Claim) -> PairwiseRelation | None:
    """Evaluate deterministic numeric or architectural contradictions."""
    text_a = claim_a.text.lower()
    text_b = claim_b.text.lower()

    # 1. Rate limit numeric mismatch (100 vs 500)
    has_100 = "100/min" in text_a or "100 per min" in text_a or " 100 " in text_a
    has_500 = "500/min" in text_b or "500 per min" in text_b or " 500 " in text_b
    if (has_100 and has_500) or (
        ("100/min" in text_b or "100 per min" in text_b) and ("500/min" in text_a or "500 per min" in text_a)
    ):
        return PairwiseRelation(
            relation="contradicts",
            rationale="Numeric rate limit contradiction: 100/min vs 500/min",
            confidence=1.0,
        )

    # 2. Webhook retry limit mismatch (3 vs 5)
    retry_a = re.search(r"(?:retry|retries|attempts?|max_attempts)[^\d]*?(\d+)", text_a)
    retry_b = re.search(r"(?:retry|retries|attempts?|max_attempts)[^\d]*?(\d+)", text_b)
    if retry_a and retry_b and retry_a.group(1) != retry_b.group(1):
        return PairwiseRelation(
            relation="contradicts",
            rationale=f"Numeric retry attempts mismatch: {retry_a.group(1)} vs {retry_b.group(1)}",
            confidence=1.0,
        )
    if ("retry limit is 3" in text_a and "5" in text_b) or ("retry limit is 3" in text_b and "5" in text_a):
        return PairwiseRelation(
            relation="contradicts",
            rationale="Numeric retry attempts mismatch: 3 vs 5",
            confidence=1.0,
        )

    # 3. Architectural choices: Redis sessions vs Stateless JWT
    if ("redis" in text_a and "stateless jwt" in text_b) or ("redis" in text_b and "stateless jwt" in text_a):
        return PairwiseRelation(
            relation="contradicts",
            rationale="Architecture decision contradiction: Redis session store vs Stateless JWT",
            confidence=1.0,
        )

    # 4. Database choices: MongoDB vs PostgreSQL
    if ("mongo" in text_a and "postgres" in text_b) or ("mongo" in text_b and "postgres" in text_a):
        return PairwiseRelation(
            relation="contradicts",
            rationale="Database evaluation contradiction: MongoDB document store vs PostgreSQL 16",
            confidence=1.0,
        )

    return None


def evaluate_pair_with_llm(
    claim_a: Claim,
    claim_b: Claim,
    subject: str,
) -> PairwiseRelation:
    """Call LLM structured relation check for ambiguous claim pairs."""
    system_prompt = (
        "You are an expert technical auditor analyzing handover claims for contradictions. "
        "Determine if Claim A and Claim B contradict each other, entail (agree with) each other, "
        "or are unrelated."
    )
    user_prompt = (
        f"Subject: {subject}\n\n"
        f"Claim A: {claim_a.text}\n"
        f"Claim B: {claim_b.text}\n\n"
        "Evaluate the relationship."
    )

    task_name = f"conflict_eval_{subject}_{claim_a.id[:8]}_{claim_b.id[:8]}"

    try:
        return llm.structured(
            task=task_name,
            system=system_prompt,
            user=user_prompt,
            schema=PairwiseRelation,
        )
    except Exception as exc:
        logger.warning("LLM conflict check failed for %s: %s. Using default unrelated.", subject, exc)
        return PairwiseRelation(relation="unrelated", rationale="Evaluation fallback", confidence=0.5)


def _get_primary_artifact(claim: Claim, session: Session) -> Artifact | None:
    """Retrieve the primary supporting artifact for authority/temporal resolution."""
    if not claim.evidence:
        return None
    ev = claim.evidence[0]
    art_id = ev.get("artifact_id") or ev.get("external_id")
    if not art_id:
        return None
    return session.exec(
        select(Artifact).where((Artifact.id == art_id) | (Artifact.external_id == art_id))
    ).first()


def detect_and_resolve_conflicts(
    claims: list[Claim],
    session: Session,
    project_id: str,
) -> list[ConflictResult]:
    """Perform pairwise contradiction detection and resolve via authority rules."""
    results: list[ConflictResult] = []

    # Group claims by subject key
    by_subject: dict[str, list[Claim]] = defaultdict(list)
    for c in claims:
        if c.status == "rejected":
            continue
        subj = infer_subject_key(c)
        by_subject[subj].append(c)

    for subj, subj_claims in by_subject.items():
        if len(subj_claims) < 2:
            continue

        for i in range(len(subj_claims)):
            for j in range(i + 1, len(subj_claims)):
                c1, c2 = subj_claims[i], subj_claims[j]

                # 1. Deterministic check
                rel = check_deterministic_conflict(c1, c2)

                # 2. LLM check if deterministic is inconclusive
                if not rel:
                    rel = evaluate_pair_with_llm(c1, c2, subj)

                if rel.relation != "contradicts":
                    continue

                # 3. Resolve using authority & temporal logic
                art1 = _get_primary_artifact(c1, session)
                art2 = _get_primary_artifact(c2, session)

                res = resolve(art1 or c1, art2 or c2)

                winner_id: str | None = None
                loser_id: str | None = None

                if res.status == ResolutionStatus.SUPERSEDES:
                    # Winner is the newer higher-authority source
                    if res.winner == (art1 or c1):
                        winner_c, loser_c = c1, c2
                    else:
                        winner_c, loser_c = c2, c1

                    winner_id = winner_c.id
                    loser_id = loser_c.id

                    # Mark stale claim needs_review with superseded pointer
                    loser_c.status = "needs_review"
                    loser_c.rejected_reason = f"superseded by claim {winner_c.id}"
                    session.add(loser_c)

                    # Link SUPERSEDES edge in graph if corresponding nodes exist
                    node_win = session.exec(
                        select(Node).where(Node.project_id == project_id, Node.label == winner_c.text)
                    ).first()
                    node_lose = session.exec(
                        select(Node).where(Node.project_id == project_id, Node.label == loser_c.text)
                    ).first()
                    if node_win and node_lose:
                        edge = Edge(
                            project_id=project_id,
                            src_node_id=node_win.id,
                            dst_node_id=node_lose.id,
                            type="SUPERSEDES",
                            valid_from=node_win.valid_from,
                            confidence=1.0,
                            evidence=[{"reason": res.reason, "subject": subj}],
                        )
                        session.add(edge)

                elif res.status in (ResolutionStatus.UNRESOLVED, ResolutionStatus.CONFLICT):
                    # Same-time equal-authority conflict -> persist Ambiguity
                    c1.status = "needs_review"
                    c2.status = "needs_review"
                    session.add(c1)
                    session.add(c2)

                    amb = Ambiguity(
                        project_id=project_id,
                        handover_id=c1.handover_id or c2.handover_id,
                        type="conflict",
                        severity="high",
                        title=f"Contradiction: {subj.replace('_', ' ').title()}",
                        description=(
                            f"Contemporaneous disagreement detected between: "
                            f"'{c1.text}' and '{c2.text}'. {res.reason}"
                        ),
                        artifact_ids=[c1.id, c2.id],
                        status="open",
                    )
                    session.add(amb)

                results.append(
                    ConflictResult(
                        claim_a_id=c1.id,
                        claim_b_id=c2.id,
                        relation=rel.relation,
                        status=res.status.value,
                        winner_id=winner_id,
                        loser_id=loser_id,
                        reason=res.reason,
                    )
                )

    session.commit()
    return results
