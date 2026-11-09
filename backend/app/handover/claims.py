"""Handover claims management, human claim creation, editing, and ambiguity resolution.

Provides:
- Filtered and paginated claims listing with ABAC sensitivity masking.
- Claim PATCH with optimistic concurrency (updated_at/version check -> 409).
- Human claim creation (requires >=1 artifact evidence OR explicit unverified=true).
- Ambiguity resolution and lead-only waiving.
- Automatic sign-off invalidation on mutation.
- Tamper-evident audit logging for all mutations.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.db import audit, utcnow
from app.errors import AppError
from app.handover.signoff import invalidate_handover_signoffs
from app.models import (
    Ambiguity,
    Claim,
    Handover,
    ProjectMember,
    User,
)
from app.policy import mask_claim
from app.verify.citations import bind_and_validate

logger = logging.getLogger("relayops.handover.claims")


def _to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


class ClaimPatchInput(BaseModel):
    text: str | None = None
    status: str | None = None  # accepted | rejected | needs_review | edited | draft
    rejected_reason: str | None = None
    expected_updated_at: datetime | None = None


class ClaimCreateInput(BaseModel):
    text: str
    section: str = "general"
    kind: str = "architecture_decision"
    evidence_artifact_ids: list[str] = Field(default_factory=list)
    unverified: bool = False
    sensitivity: int = 1


class AmbiguityResolveInput(BaseModel):
    resolution_note: str
    expected_updated_at: datetime | None = None


class AmbiguityWaiveInput(BaseModel):
    reason: str
    expected_updated_at: datetime | None = None


def list_handover_claims(
    session: Session,
    handover_id: str,
    user: User,
    *,
    section: str | None = None,
    status: str | None = None,
    kind: str | None = None,
    min_sensitivity: int | None = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: str | None = None,
    sort_order: str = "asc",
) -> dict[str, Any]:
    """List claims for a handover with filtering, pagination, and ABAC sensitivity masking."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    query = select(Claim).where(Claim.handover_id == handover_id)

    if section:
        query = query.where(Claim.section == section)
    if status:
        query = query.where(Claim.status == status)
    if kind:
        query = query.where(Claim.kind == kind)
    if min_sensitivity is not None:
        query = query.where(Claim.sensitivity >= min_sensitivity)

    # Get total count before pagination
    total_items = session.exec(query).all()
    total = len(total_items)

    if sort_by == "created_at":
        order_col = Claim.created_at.desc() if sort_order == "desc" else Claim.created_at.asc()
        query = query.order_by(order_col)
    elif sort_by == "confidence":
        order_col = Claim.confidence.desc() if sort_order == "desc" else Claim.confidence.asc()
        query = query.order_by(order_col)
    else:
        query = query.order_by(Claim.order_index.asc(), Claim.id.asc())

    paged_claims = session.exec(query.offset(offset).limit(limit)).all()

    # Mask according to user clearance
    items = [mask_claim(c, user) for c in paged_claims]
    page = (offset // limit) + 1 if limit else 1

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "page": page,
        "page_size": limit,
    }


def patch_claim(
    session: Session,
    claim_id: str,
    user: User,
    data: ClaimPatchInput,
) -> dict[str, Any]:
    """Update a claim with optimistic concurrency check, state machine validation, and audit logging."""
    claim = session.get(Claim, claim_id)
    if not claim:
        raise AppError("NOT_FOUND", "Claim not found", status_code=404)

    # Optimistic concurrency check
    if data.expected_updated_at is not None:
        t_cur = _to_naive_utc(claim.updated_at)
        t_exp = _to_naive_utc(data.expected_updated_at)
        diff_sec = abs((t_cur - t_exp).total_seconds())
        if diff_sec > 0.005:
            raise AppError(
                "CONFLICT",
                "Claim was modified concurrently by another user. Please refresh and retry.",
                status_code=409,
                details={
                    "current_updated_at": claim.updated_at.isoformat(),
                    "expected_updated_at": data.expected_updated_at.isoformat(),
                },
            )

    text_changed = False
    old_status = claim.status

    # 1. Text edit
    if data.text is not None and data.text != claim.text:
        claim.text = data.text
        claim.status = "edited"
        claim.edited_by = user.id
        text_changed = True

    # 2. Status change
    if data.status is not None:
        if data.status == "rejected":
            reason = data.rejected_reason or claim.rejected_reason
            if not reason or not reason.strip():
                raise AppError(
                    "VALIDATION_ERROR",
                    "A rejection reason is required when rejecting a claim",
                    status_code=422,
                )
            claim.status = "rejected"
            claim.rejected_reason = reason.strip()
        elif data.status == "accepted":
            claim.status = "accepted"
            claim.rejected_reason = None
        elif data.status in ("needs_review", "edited", "draft"):
            claim.status = data.status
            if data.status == "edited":
                claim.edited_by = user.id
        else:
            raise AppError("BAD_REQUEST", f"Invalid claim status '{data.status}'", status_code=400)

    claim.updated_at = utcnow()
    session.add(claim)

    # Invalidate sign-offs if this claim belongs to a handover
    if claim.handover_id:
        invalidate_handover_signoffs(
            session,
            claim.handover_id,
            reason=f"Claim {claim.id} updated by {user.email}",
            actor_id=user.id,
        )

    # Audit log
    audit(
        session,
        actor_id=user.id,
        action="claim_updated",
        target_type="claim",
        target_id=claim.id,
        payload={
            "handover_id": claim.handover_id,
            "text_changed": text_changed,
            "old_status": old_status,
            "new_status": claim.status,
            "rejected_reason": claim.rejected_reason,
        },
    )

    session.commit()
    session.refresh(claim)
    return mask_claim(claim, user)


def create_human_claim(
    session: Session,
    handover_id: str,
    user: User,
    data: ClaimCreateInput,
) -> dict[str, Any]:
    """Create a human-asserted claim for a handover."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    # Product rule: requires >= 1 evidence artifact ID OR explicit unverified=true
    if not data.evidence_artifact_ids and not data.unverified:
        raise AppError(
            "VALIDATION_ERROR",
            "Human-added claim requires >= 1 evidence artifact ID or explicit unverified=true",
            status_code=422,
        )

    if data.unverified:
        # Author-asserted claim
        ev_list = [
            {
                "artifact_id": None,
                "source_uri": "author-asserted",
                "snippet": "Unverified (author-asserted)",
                "unverified": True,
                "sensitivity": data.sensitivity,
            }
        ]
        status = "needs_review"
        confidence = 0.5
        sensitivity = data.sensitivity
    else:
        # Grounded in artifact evidence
        ev_list = [{"artifact_id": aid} for aid in data.evidence_artifact_ids]
        status = "accepted"
        confidence = 1.0
        sensitivity = data.sensitivity

    claim = Claim(
        project_id=handover.project_id,
        handover_id=handover_id,
        section=data.section,
        kind=data.kind,
        text=data.text,
        status=status,
        confidence=confidence,
        sensitivity=sensitivity,
        evidence=ev_list,
        origin="human",
        edited_by=user.id,
    )

    # Bind citations against artifacts if artifacts were provided
    if not data.unverified:
        bind_and_validate(claim, session, project_id=handover.project_id)

    session.add(claim)

    # Invalidate sign-offs on this handover
    invalidate_handover_signoffs(
        session,
        handover_id,
        reason=f"New human claim added by {user.email}",
        actor_id=user.id,
    )

    # Audit log
    audit(
        session,
        actor_id=user.id,
        action="claim_created",
        target_type="claim",
        target_id=claim.id,
        payload={
            "handover_id": handover_id,
            "section": claim.section,
            "unverified": data.unverified,
            "status": claim.status,
        },
    )

    session.commit()
    session.refresh(claim)
    return mask_claim(claim, user)


# ---------------------------------------------------------------------------
# Ambiguity Resolution & Waiving
# ---------------------------------------------------------------------------


def list_handover_ambiguities(
    session: Session,
    handover_id: str,
    *,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List ambiguities associated with a handover."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    query = select(Ambiguity).where(Ambiguity.handover_id == handover_id)
    if status:
        query = query.where(Ambiguity.status == status)
    if severity:
        query = query.where(Ambiguity.severity == severity)

    total_items = session.exec(query).all()
    total = len(total_items)

    ambs = session.exec(query.order_by(Ambiguity.id.asc()).offset(offset).limit(limit)).all()
    page = (offset // limit) + 1 if limit else 1

    return {
        "items": [a.model_dump(mode="json") for a in ambs],
        "total": total,
        "limit": limit,
        "offset": offset,
        "page": page,
        "page_size": limit,
    }


def resolve_ambiguity(
    session: Session,
    ambiguity_id: str,
    user: User,
    data: AmbiguityResolveInput,
) -> Ambiguity:
    """Resolve an open ambiguity with a required resolution note."""
    amb = session.get(Ambiguity, ambiguity_id)
    if not amb:
        raise AppError("NOT_FOUND", "Ambiguity not found", status_code=404)

    if not data.resolution_note or not data.resolution_note.strip():
        raise AppError(
            "VALIDATION_ERROR",
            "Resolution note is required to resolve an ambiguity",
            status_code=422,
        )

    # Optimistic concurrency check
    if data.expected_updated_at is not None:
        t_cur = _to_naive_utc(amb.updated_at)
        t_exp = _to_naive_utc(data.expected_updated_at)
        diff_sec = abs((t_cur - t_exp).total_seconds())
        if diff_sec > 0.005:
            raise AppError(
                "CONFLICT",
                "Ambiguity was modified concurrently by another user. Please refresh and retry.",
                status_code=409,
            )

    amb.status = "resolved"
    amb.resolution_note = data.resolution_note.strip()
    amb.resolved_by = user.id
    amb.updated_at = utcnow()
    session.add(amb)

    # Invalidate sign-offs if associated with a handover
    if amb.handover_id:
        invalidate_handover_signoffs(
            session,
            amb.handover_id,
            reason=f"Ambiguity {amb.id} resolved by {user.email}",
            actor_id=user.id,
        )

    # Audit log
    audit(
        session,
        actor_id=user.id,
        action="ambiguity_resolved",
        target_type="ambiguity",
        target_id=amb.id,
        payload={"handover_id": amb.handover_id, "resolution_note": amb.resolution_note},
    )

    session.commit()
    session.refresh(amb)
    return amb


def waive_ambiguity(
    session: Session,
    ambiguity_id: str,
    user: User,
    data: AmbiguityWaiveInput,
) -> Ambiguity:
    """Waive an ambiguity. Restricted strictly to the project lead."""
    amb = session.get(Ambiguity, ambiguity_id)
    if not amb:
        raise AppError("NOT_FOUND", "Ambiguity not found", status_code=404)

    if not data.reason or not data.reason.strip():
        raise AppError(
            "VALIDATION_ERROR",
            "Reason is required to waive an ambiguity",
            status_code=422,
        )

    # Role verification: ONLY LEAD can waive an ambiguity
    is_lead = user.role == "lead"
    if not is_lead and amb.handover_id:
        handover = session.get(Handover, amb.handover_id)
        if handover and handover.lead_user_id == user.id:
            is_lead = True

    if not is_lead and amb.project_id:
        member = session.exec(
            select(ProjectMember).where(
                ProjectMember.project_id == amb.project_id,
                ProjectMember.user_id == user.id,
                ProjectMember.project_role == "lead",
            )
        ).first()
        if member:
            is_lead = True

    if not is_lead:
        raise AppError("FORBIDDEN", "Only project leads are authorized to waive ambiguities", status_code=403)

    # Optimistic concurrency check
    if data.expected_updated_at is not None:
        t_cur = _to_naive_utc(amb.updated_at)
        t_exp = _to_naive_utc(data.expected_updated_at)
        diff_sec = abs((t_cur - t_exp).total_seconds())
        if diff_sec > 0.005:
            raise AppError(
                "CONFLICT",
                "Ambiguity was modified concurrently by another user. Please refresh and retry.",
                status_code=409,
            )

    amb.status = "waived"
    amb.resolution_note = data.reason.strip()
    amb.resolved_by = user.id
    amb.updated_at = utcnow()
    session.add(amb)

    if amb.handover_id:
        invalidate_handover_signoffs(
            session,
            amb.handover_id,
            reason=f"Ambiguity {amb.id} waived by lead {user.email}",
            actor_id=user.id,
        )

    # Audit log
    audit(
        session,
        actor_id=user.id,
        action="ambiguity_waived",
        target_type="ambiguity",
        target_id=amb.id,
        payload={"handover_id": amb.handover_id, "waive_reason": amb.resolution_note},
    )

    session.commit()
    session.refresh(amb)
    return amb
