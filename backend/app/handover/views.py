"""Role-scoped handover views, delivery transition, and glossary enrichment.

Builds successor-facing perspectives from the LATEST SIGNED version:
- maintainer: full technical view.
- junior: adds 'why it matters' glossary notes explaining rationale.
- contractor: clearance <= 1, credentials/private escalations masked.
- auditor: metadata + scorecard + audit chain; raw bodies withheld.
Previewing 'as' another role is strictly restricted to project leads.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from sqlmodel import Session, select

from app.db import audit, utcnow
from app.errors import AppError
from app.handover.signoff import verify_handover
from app.models import (
    Handover,
    HandoverVersion,
    Signoff,
    User,
)
from app.policy import mask_claim

logger = logging.getLogger("relayops.handover.views")

# Technical glossary providing "why it matters" context for junior engineers
JUNIOR_GLOSSARY: dict[str, dict[str, str]] = {
    "webhook": {
        "term": "Idempotent Webhook Dispatch",
        "why_it_matters": (
            "Payment webhooks can arrive multiple times due to network retries. "
            "Without idempotency keys and exponential backoff, merchant balances could be credited twice."
        ),
    },
    "webhook_retry_policy": {
        "term": "Exponential Backoff & Max Attempts",
        "why_it_matters": (
            "Prevents overwhelming downstream acquirers during outages while guaranteeing delivery "
            "once third-party services recover."
        ),
    },
    "database": {
        "term": "ACID Ledger Transactions in PostgreSQL 16",
        "why_it_matters": (
            "Financial ledgers require strict transactional isolation (SERIALIZABLE or READ COMMITTED) "
            "to prevent double-spend race conditions."
        ),
    },
    "database_choice": {
        "term": "Relational PostgreSQL vs Document Store",
        "why_it_matters": (
            "Ledger transactions demand row-level locking and strict foreign key integrity, which relational "
            "engines provide out of the box."
        ),
    },
    "session_caching": {
        "term": "Stateless JWT Authentication",
        "why_it_matters": (
            "Eliminates server-side session affinity, allowing API gateway containers to scale horizontally "
            "without centralized Redis bottleneck."
        ),
    },
    "idempotency_keys": {
        "term": "Idempotency Key Deduplication",
        "why_it_matters": (
            "Clients supply unique UUIDs per transfer request so network timeouts do not duplicate charges."
        ),
    },
    "rate_limit": {
        "term": "Token-Bucket Rate Limiting",
        "why_it_matters": (
            "Protects shared payment infrastructure from denial-of-service and enforces merchant SLA tiers."
        ),
    },
}


def mask_scorecard(
    scorecard: dict[str, Any],
    claims: list[dict[str, Any]],
    eff_clearance: int,
    viewing_role: str,
) -> dict[str, Any]:
    """Mask sensitive claim texts within scorecard claim_scores for low-clearance viewers or auditors."""
    if not scorecard:
        return {}
    sc = copy.deepcopy(scorecard)
    claim_sens_map = {c.get("id"): c.get("sensitivity", 1) for c in claims if "id" in c}
    claim_scores = sc.get("claim_scores", [])
    if isinstance(claim_scores, list):
        for cs in claim_scores:
            cid = cs.get("claim_id")
            sens = claim_sens_map.get(cid, 1)
            if viewing_role == "auditor":
                cs["text"] = "[Audit Mode: Text withheld]"
            elif sens > eff_clearance:
                cs["text"] = f"[Restricted: requires clearance {sens}]"
    return sc


def get_latest_signed_version(
    session: Session, handover_id: str, allow_latest_for_lead: bool = False
) -> HandoverVersion:
    """Retrieve the latest HandoverVersion that has dual sign-offs (or signed status)."""
    # 1. Look for signed version in signoff table with both outgoing and lead
    signoffs = session.exec(select(Signoff).where(Signoff.handover_id == handover_id)).all()
    roles_by_version: dict[int, set[str]] = {}
    for s in signoffs:
        roles_by_version.setdefault(s.version, set()).add(s.role)

    signed_versions = [v for v, roles in roles_by_version.items() if "outgoing" in roles and "lead" in roles]

    if signed_versions:
        target_v = max(signed_versions)
        hv = session.exec(
            select(HandoverVersion).where(
                HandoverVersion.handover_id == handover_id,
                HandoverVersion.version == target_v,
            )
        ).first()
        if hv:
            return hv

    # 2. Check if handover is marked signed/delivered
    handover = session.get(Handover, handover_id)
    if handover and handover.status in ("signed", "delivered"):
        hv = session.exec(
            select(HandoverVersion)
            .where(HandoverVersion.handover_id == handover_id)
            .order_by(HandoverVersion.version.desc())
            .limit(1)
        ).first()
        if hv:
            return hv

    # 3. For lead preview before dual sign-off, allow falling back to latest snapshot
    if allow_latest_for_lead:
        hv = session.exec(
            select(HandoverVersion)
            .where(HandoverVersion.handover_id == handover_id)
            .order_by(HandoverVersion.version.desc())
            .limit(1)
        ).first()
        if hv:
            return hv

    raise AppError(
        "PRECONDITION_FAILED",
        "No signed handover version is available. A handover must be signed by both outgoing contributor "
        "and lead before viewing or delivery.",
        status_code=400,
    )


def build_handover_view(
    session: Session,
    handover_id: str,
    user: User,
    *,
    as_role: str | None = None,
) -> dict[str, Any]:
    """Build role-scoped successor view from the latest signed snapshot."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    is_lead = user.role == "lead" or handover.lead_user_id == user.id

    # RBAC: Only lead can preview "as" another role
    if as_role:
        target_role = as_role.lower()
        if not is_lead and target_role != user.role.lower():
            raise AppError(
                "FORBIDDEN",
                f"Only project leads can preview the handover as '{as_role}'.",
                status_code=403,
            )
        viewing_role = target_role
    else:
        viewing_role = user.role.lower()

    # Determine effective clearance for viewing role
    eff_clearance = min(user.clearance, 1) if viewing_role in ("contractor", "auditor") else user.clearance

    # Construct synthetic viewer for policy checks
    viewer_context = {
        "id": user.id,
        "email": user.email,
        "role": viewing_role,
        "clearance": eff_clearance,
    }

    # Fetch latest signed version snapshot (or latest snapshot if lead is previewing)
    version_rec = get_latest_signed_version(session, handover_id, allow_latest_for_lead=is_lead)
    snapshot = version_rec.snapshot or {}

    raw_claims = snapshot.get("claims", [])
    raw_ambiguities = snapshot.get("ambiguities", [])
    raw_plan = snapshot.get("plan_items", [])
    raw_scorecard = snapshot.get("scorecard", {})

    # Apply policy masking to claims
    masked_claims: list[dict[str, Any]] = []
    for c in raw_claims:
        masked = mask_claim(c, viewer_context)
        if viewing_role == "auditor":
            # Auditors receive metadata, confidence, and validation status, but NO claim bodies
            masked["text"] = "[Audit Mode: Text withheld]"
            masked["evidence"] = []
            masked["audit_mode"] = True
        masked_claims.append(masked)

    # Filter ambiguities by clearance if needed
    visible_ambiguities: list[dict[str, Any]] = []
    for a in raw_ambiguities:
        if viewing_role == "contractor" and a.get("severity") == "high":
            # Mask sensitive blocker details for external contractor
            a_copy = dict(a)
            if (
                "credentials" in a_copy.get("description", "").lower()
                or "pricing" in a_copy.get("description", "").lower()
            ):
                a_copy["description"] = "Restricted: high-severity internal escalation"
            visible_ambiguities.append(a_copy)
        elif viewing_role == "auditor":
            a_copy = dict(a)
            a_copy["description"] = "[Audit Mode: Details withheld]"
            visible_ambiguities.append(a_copy)
        else:
            visible_ambiguities.append(a)

    # Enrich junior view with "why it matters" glossary
    glossary_items: list[dict[str, Any]] = []
    if viewing_role in ("junior", "successor"):
        seen_topics: set[str] = set()
        for c in masked_claims:
            topic = c.get("section", "")
            if topic in JUNIOR_GLOSSARY and topic not in seen_topics:
                seen_topics.add(topic)
                glossary_items.append(JUNIOR_GLOSSARY[topic])

    # Fetch signatures for verification display
    signoffs = session.exec(
        select(Signoff)
        .where(Signoff.handover_id == handover_id, Signoff.version == version_rec.version)
        .order_by(Signoff.signed_at.asc())
    ).all()

    signatures = [
        {
            "user_id": s.user_id,
            "role": s.role,
            "signed_at": s.signed_at.isoformat(),
            "signature": s.signature,
            "comment": s.comment,
        }
        for s in signoffs
    ]

    # Audit chain & redaction summary for auditor view
    audit_chain_info = None
    redaction_summary = None
    if viewing_role == "auditor":
        audit_chain_info = verify_handover(session, handover_id)
        from app.models import Artifact, RedactionEvent
        events = session.exec(
            select(RedactionEvent)
            .join(Artifact, RedactionEvent.artifact_id == Artifact.id)
            .where(Artifact.project_id == handover.project_id)
        ).all()
        rule_counts: dict[str, int] = {}
        for ev in events:
            rule_counts[ev.rule] = rule_counts.get(ev.rule, 0) + 1
        redaction_summary = {
            "total_redactions": len(events),
            "rules": [
                {"rule": rule, "count": count, "sample_masked": f"[{rule.upper()}_REDACTED]"}
                for rule, count in rule_counts.items()
            ],
        }

    masked_scorecard = mask_scorecard(raw_scorecard, raw_claims, eff_clearance, viewing_role)

    return {
        "handover_id": handover_id,
        "project_id": handover.project_id,
        "version": version_rec.version,
        "hash": version_rec.hash,
        "viewing_role": viewing_role,
        "effective_clearance": eff_clearance,
        "status": handover.status,
        "claims": masked_claims,
        "ambiguities": visible_ambiguities,
        "plan_items": raw_plan,
        "scorecard": masked_scorecard,
        "glossary": glossary_items if glossary_items else None,
        "signatures": signatures,
        "audit_verification": audit_chain_info,
        "redaction_summary": redaction_summary,
    }


def deliver_handover(session: Session, handover_id: str, user: User) -> dict[str, Any]:
    """Deliver a signed handover to the successor. Restricted to project lead."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    is_lead = user.role == "lead" or handover.lead_user_id == user.id
    if not is_lead:
        raise AppError("FORBIDDEN", "Only the project lead can authorize handover delivery", status_code=403)

    if handover.status != "signed":
        raise AppError(
            "PRECONDITION_FAILED",
            f"Handover cannot be delivered in status '{handover.status}'. "
            "It must be fully 'signed' by both parties.",
            status_code=400,
        )

    now = utcnow()
    handover.status = "delivered"
    handover.updated_at = now
    session.add(handover)

    # Audit log
    audit(
        session,
        actor_id=user.id,
        action="handover_delivered",
        target_type="handover",
        target_id=handover_id,
        payload={
            "delivered_at": now.isoformat(),
            "successor_user_id": handover.successor_user_id,
            "version": handover.current_version,
        },
    )

    session.commit()
    session.refresh(handover)
    logger.info("Handover %s DELIVERED to successor %s", handover_id, handover.successor_user_id)

    return {
        "handover_id": handover_id,
        "status": "delivered",
        "delivered_at": now.isoformat(),
        "successor_user_id": handover.successor_user_id,
        "notification": f"Handover delivered to successor {handover.successor_user_id}.",
    }
