"""Router for handover review workflows: claims, ambiguities, versioning, and dual sign-off."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.errors import AppError
from app.handover.claims import (
    AmbiguityResolveInput,
    AmbiguityWaiveInput,
    ClaimCreateInput,
    ClaimPatchInput,
    create_human_claim,
    list_handover_ambiguities,
    list_handover_claims,
    patch_claim,
    resolve_ambiguity,
    waive_ambiguity,
)
from app.handover.signoff import (
    execute_signoff,
    verify_handover,
)
from app.handover.versions import (
    create_snapshot,
    diff_versions,
)
from app.models import Ambiguity, Claim, Handover, HandoverVersion, Signoff, User
from app.schemas import (
    AmbiguityRead,
    ClaimRead,
    ConflictItemRead,
    HandoverVerificationRead,
    HandoverVersionRead,
    SignoffCreateRequest,
    SignoffExecutionResponse,
    SignoffRead,
    SnapshotCreateRequest,
    VersionDiffRead,
)

logger = logging.getLogger("relayops.routers.review")
router = APIRouter(tags=["review"])


# ---------------------------------------------------------------------------
# 1. Claims Review Endpoints
# ---------------------------------------------------------------------------


@router.get("/handovers/{handover_id}/claims")
def get_claims(
    handover_id: str,
    response: Response,
    section: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    kind: str | None = Query(default=None),
    min_sensitivity: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="asc"),
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int | None = Query(default=None, ge=0),
    paged: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve claims associated with a handover with filtering and pagination."""
    eff_limit = limit if limit is not None else page_size
    eff_offset = offset if offset is not None else (page - 1) * page_size
    eff_page = (eff_offset // eff_limit) + 1 if eff_limit else 1

    res = list_handover_claims(
        session,
        handover_id,
        current_user,
        section=section,
        status=status_filter,
        kind=kind,
        min_sensitivity=min_sensitivity,
        limit=eff_limit,
        offset=eff_offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    response.headers["X-Total-Count"] = str(res["total"])
    response.headers["X-Limit"] = str(res["limit"])
    response.headers["X-Offset"] = str(res["offset"])
    response.headers["X-Page"] = str(eff_page)
    response.headers["X-Page-Size"] = str(eff_limit)

    if paged:
        return {
            "items": res["items"],
            "total": res["total"],
            "page": eff_page,
            "page_size": eff_limit,
        }
    return res["items"]


@router.patch("/claims/{claim_id}", response_model=ClaimRead)
def update_claim(
    claim_id: str,
    payload: ClaimPatchInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ClaimRead:
    """Edit, accept, reject, or mark a claim as needs_review with optimistic concurrency check."""
    return patch_claim(session, claim_id, current_user, payload)


@router.post(
    "/handovers/{handover_id}/claims",
    response_model=ClaimRead,
    status_code=status.HTTP_201_CREATED,
)
def add_human_claim(
    handover_id: str,
    payload: ClaimCreateInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ClaimRead:
    """Add a human-asserted claim (requires evidence artifact ID or unverified=true)."""
    return create_human_claim(session, handover_id, current_user, payload)
    """Add a human-asserted claim (requires evidence artifact ID or unverified=true)."""
    return create_human_claim(session, handover_id, current_user, payload)


# ---------------------------------------------------------------------------
# 2. Ambiguity Review Endpoints
# ---------------------------------------------------------------------------


@router.get("/handovers/{handover_id}/ambiguities")
def get_ambiguities(
    handover_id: str,
    response: Response,
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int | None = Query(default=None, ge=0),
    paged: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List ambiguities for a handover."""
    eff_limit = limit if limit is not None else page_size
    eff_offset = offset if offset is not None else (page - 1) * page_size
    eff_page = (eff_offset // eff_limit) + 1 if eff_limit else 1

    res = list_handover_ambiguities(
        session,
        handover_id,
        status=status_filter,
        severity=severity,
        limit=eff_limit,
        offset=eff_offset,
    )
    response.headers["X-Total-Count"] = str(res["total"])
    response.headers["X-Limit"] = str(res["limit"])
    response.headers["X-Offset"] = str(res["offset"])
    response.headers["X-Page"] = str(eff_page)
    response.headers["X-Page-Size"] = str(eff_limit)

    if paged:
        return {
            "items": res["items"],
            "total": res["total"],
            "page": eff_page,
            "page_size": eff_limit,
        }
    return res["items"]


@router.post("/ambiguities/{ambiguity_id}/resolve", response_model=AmbiguityRead)
def resolve_ambiguity_endpoint(
    ambiguity_id: str,
    payload: AmbiguityResolveInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AmbiguityRead:
    """Resolve an ambiguity with a required resolution note."""
    amb = resolve_ambiguity(session, ambiguity_id, current_user, payload)
    return AmbiguityRead.model_validate(amb)


@router.post("/ambiguities/{ambiguity_id}/waive", response_model=AmbiguityRead)
def waive_ambiguity_endpoint(
    ambiguity_id: str,
    payload: AmbiguityWaiveInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AmbiguityRead:
    """Waive an ambiguity. Restricted strictly to project lead."""
    amb = waive_ambiguity(session, ambiguity_id, current_user, payload)
    return AmbiguityRead.model_validate(amb)


@router.get("/handovers/{handover_id}/conflicts", response_model=list[ConflictItemRead])
def get_conflicts(
    handover_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[ConflictItemRead]:
    """Retrieve detected conflicts and contradictions for the handover."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    # 1. Conflict ambiguities
    ambs = session.exec(
        select(Ambiguity).where(
            Ambiguity.handover_id == handover_id,
            Ambiguity.type == "conflict",
        )
    ).all()

    conflicts: list[ConflictItemRead] = []

    def get_claim_authority(c: Claim) -> float:
        if not c.evidence:
            return 0.5
        auths = [float(e.get("authority", 0.5)) for e in c.evidence if isinstance(e, dict)]
        return max(auths) if auths else 0.5

    for amb in ambs:
        c1 = session.get(Claim, amb.artifact_ids[0]) if len(amb.artifact_ids) > 0 else None
        c2 = session.get(Claim, amb.artifact_ids[1]) if len(amb.artifact_ids) > 1 else None

        conflicts.append(
            ConflictItemRead(
                id=amb.id,
                handover_id=handover_id,
                subject=amb.title.replace("Contradiction: ", ""),
                title=amb.title,
                description=amb.description,
                status=amb.status,
                claim_a_id=c1.id if c1 else (amb.artifact_ids[0] if len(amb.artifact_ids) > 0 else "unknown"),
                claim_a_text=c1.text if c1 else "",
                claim_a_authority=get_claim_authority(c1) if c1 else 0.5,
                claim_a_created_at=c1.created_at.isoformat() if c1 else None,
                claim_b_id=c2.id if c2 else (amb.artifact_ids[1] if len(amb.artifact_ids) > 1 else "unknown"),
                claim_b_text=c2.text if c2 else "",
                claim_b_authority=get_claim_authority(c2) if c2 else 0.5,
                claim_b_created_at=c2.created_at.isoformat() if c2 else None,
                ambiguity_id=amb.id,
                chosen_resolution=amb.resolution_note,
            )
        )

    # 2. Claims marked superseded by another claim
    superseded_claims = session.exec(
        select(Claim).where(
            Claim.handover_id == handover_id,
            Claim.rejected_reason.like("superseded by claim %"),  # type: ignore
        )
    ).all()

    for sc in superseded_claims:
        if sc.rejected_reason:
            winner_id = sc.rejected_reason.split("superseded by claim ")[-1].strip()
            winner_c = session.get(Claim, winner_id)
            if winner_c:
                conflicts.append(
                    ConflictItemRead(
                        id=f"conflict_{sc.id}_{winner_c.id}",
                        handover_id=handover_id,
                        subject=sc.section,
                        title=f"Superseded Decision: {sc.section.title()}",
                        description=f"Newer higher-authority claim '{winner_c.text}' supersedes '{sc.text}'.",
                        status="superseded",
                        claim_a_id=sc.id,
                        claim_a_text=sc.text,
                        claim_a_authority=get_claim_authority(sc),
                        claim_a_created_at=sc.created_at.isoformat(),
                        claim_b_id=winner_c.id,
                        claim_b_text=winner_c.text,
                        claim_b_authority=get_claim_authority(winner_c),
                        claim_b_created_at=winner_c.created_at.isoformat(),
                        winner_claim_id=winner_c.id,
                        loser_claim_id=sc.id,
                        chosen_resolution="Newer source authority wins",
                    )
                )

    return conflicts


# ---------------------------------------------------------------------------
# 3. Versioning & Diff Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/handovers/{handover_id}/snapshot",
    response_model=HandoverVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot_endpoint(
    handover_id: str,
    payload: SnapshotCreateRequest | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HandoverVersionRead:
    """Freeze current claims, ambiguities, plan, and scorecard into a new cryptographic snapshot."""
    reason = payload.reason if payload else ""
    hv = create_snapshot(session, handover_id, actor_id=current_user.id, reason=reason)
    return HandoverVersionRead.model_validate(hv)


@router.get(
    "/handovers/{handover_id}/versions",
    response_model=list[HandoverVersionRead],
)
def get_versions(
    handover_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[HandoverVersionRead]:
    """List all version snapshots for a handover."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    versions = session.exec(
        select(HandoverVersion)
        .where(HandoverVersion.handover_id == handover_id)
        .order_by(HandoverVersion.version.asc())
    ).all()
    return [HandoverVersionRead.model_validate(v) for v in versions]


@router.get("/handovers/{handover_id}/versions/diff", response_model=VersionDiffRead)
@router.get("/handovers/{handover_id}/diff", response_model=VersionDiffRead)
def get_version_diff(
    handover_id: str,
    v1: int = Query(..., description="Base version number"),
    v2: int = Query(..., description="Target version number"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> VersionDiffRead:
    """Compute structured claim and ambiguity diffs between two versions."""
    rec_v1 = session.exec(
        select(HandoverVersion).where(
            HandoverVersion.handover_id == handover_id,
            HandoverVersion.version == v1,
        )
    ).first()
    if not rec_v1:
        raise AppError("NOT_FOUND", f"Version {v1} not found", status_code=404)

    rec_v2 = session.exec(
        select(HandoverVersion).where(
            HandoverVersion.handover_id == handover_id,
            HandoverVersion.version == v2,
        )
    ).first()
    if not rec_v2:
        raise AppError("NOT_FOUND", f"Version {v2} not found", status_code=404)

    return VersionDiffRead.model_validate(diff_versions(rec_v1, rec_v2))


# ---------------------------------------------------------------------------
# 4. Sign-off & Verification Endpoints
# ---------------------------------------------------------------------------


@router.post("/handovers/{handover_id}/signoff", response_model=SignoffExecutionResponse)
def signoff_handover(
    handover_id: str,
    payload: SignoffCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SignoffExecutionResponse:
    """Execute dual sign-off (outgoing or lead) on latest snapshot version."""
    res = execute_signoff(
        session,
        handover_id,
        current_user,
        version=payload.version,
        comment=payload.comment,
    )
    return SignoffExecutionResponse.model_validate(res)


@router.get(
    "/handovers/{handover_id}/signoffs",
    response_model=list[SignoffRead],
)
def list_signoffs(
    handover_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[SignoffRead]:
    """List sign-offs for a handover."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    signoffs = session.exec(
        select(Signoff).where(Signoff.handover_id == handover_id).order_by(Signoff.signed_at.asc())
    ).all()
    return [SignoffRead.model_validate(s) for s in signoffs]


@router.get("/handovers/{handover_id}/verify", response_model=HandoverVerificationRead)
def verify_handover_integrity(
    handover_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HandoverVerificationRead:
    """Verify cryptographic hash chain of snapshots and authenticity of sign-off HMAC signatures."""
    res = verify_handover(session, handover_id)
    return HandoverVerificationRead.model_validate(res)
