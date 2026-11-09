"""Dual sign-off state machine, HMAC cryptographic signing, and chain verification.

Non-negotiable product rule #5:
A handover cannot be delivered until BOTH the outgoing contributor and the lead sign off.
Signatures are HMAC-SHA256 over:
    handover_id|version|snapshot_hash|user_id|timestamp
Any subsequent edit invalidates signatures and requires a fresh snapshot.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from sqlmodel import Session, select

from app.config import get_settings
from app.db import audit, utcnow
from app.errors import AppError
from app.handover.versions import compute_version_hash
from app.models import (
    Ambiguity,
    Claim,
    Handover,
    HandoverVersion,
    Signoff,
    User,
)

logger = logging.getLogger("relayops.handover.signoff")


def compute_signoff_hmac(
    secret_key: str,
    handover_id: str,
    version: int,
    version_hash: str,
    user_id: str,
    timestamp_str: str,
) -> str:
    """Compute cryptographic HMAC-SHA256 signature for a sign-off event."""
    msg = f"{handover_id}|{version}|{version_hash}|{user_id}|{timestamp_str}"
    return hmac.new(secret_key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def invalidate_handover_signoffs(
    session: Session,
    handover_id: str,
    *,
    reason: str,
    actor_id: str | None = None,
) -> int:
    """Invalidate existing sign-offs when claims, ambiguities, or plan items are edited."""
    signoffs = session.exec(select(Signoff).where(Signoff.handover_id == handover_id)).all()
    if not signoffs:
        return 0

    count = len(signoffs)
    for s in signoffs:
        session.delete(s)

    handover = session.get(Handover, handover_id)
    if handover and handover.status == "signed":
        handover.status = "in_review"
        handover.updated_at = utcnow()
        session.add(handover)

    audit(
        session,
        actor_id=actor_id,
        action="signoffs_invalidated",
        target_type="handover",
        target_id=handover_id,
        payload={"reason": reason, "invalidated_count": count},
    )
    session.commit()
    logger.info("Invalidated %d sign-offs for handover %s due to: %s", count, handover_id, reason)
    return count


def execute_signoff(
    session: Session,
    handover_id: str,
    user: User,
    *,
    version: int,
    comment: str = "",
    secret_key: str | None = None,
) -> dict[str, Any]:
    """Execute sign-off for a handover version with dual sign-off validation."""
    key = secret_key or get_settings().secret_key

    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    # 1. Role verification: allowed only for outgoing + lead
    is_outgoing = handover.outgoing_user_id == user.id or user.role == "outgoing"
    is_lead = handover.lead_user_id == user.id or user.role == "lead"

    if not (is_outgoing or is_lead):
        raise AppError(
            "FORBIDDEN",
            "Sign-off is restricted to the outgoing contributor and the project lead",
            status_code=403,
        )

    signer_role = "outgoing" if is_outgoing else "lead"

    # 2. Must be on the latest snapshot version
    if version != handover.current_version:
        raise AppError(
            "BAD_REQUEST",
            f"Cannot sign off on stale version {version}; latest version is {handover.current_version}",
            status_code=400,
            details={"requested_version": version, "latest_version": handover.current_version},
        )

    # 3. Blocked if any claim is still in 'draft' status
    draft_claims = session.exec(
        select(Claim).where(Claim.handover_id == handover_id, Claim.status == "draft")
    ).all()
    if draft_claims:
        raise AppError(
            "PRECONDITION_FAILED",
            f"Sign-off blocked: {len(draft_claims)} claims are still in 'draft' status. "
            f"All claims must be accepted, edited, or rejected before sign-off.",
            status_code=400,
            details={"draft_claims_count": len(draft_claims)},
        )

    # 4. Blocked if open HIGH-severity ambiguities remain (unless waived by lead)
    open_high_ambs = session.exec(
        select(Ambiguity).where(
            Ambiguity.handover_id == handover_id,
            Ambiguity.severity == "high",
            Ambiguity.status == "open",
        )
    ).all()
    if open_high_ambs:
        raise AppError(
            "PRECONDITION_FAILED",
            f"Sign-off blocked: {len(open_high_ambs)} open HIGH-severity ambiguities remain. "
            f"Resolve or waive them before signing off.",
            status_code=400,
            details={"open_high_ambiguities_count": len(open_high_ambs)},
        )

    # 5. Fetch HandoverVersion snapshot record
    hv = session.exec(
        select(HandoverVersion).where(
            HandoverVersion.handover_id == handover_id,
            HandoverVersion.version == version,
        )
    ).first()
    if not hv:
        raise AppError(
            "NOT_FOUND",
            f"Snapshot version {version} not found for handover {handover_id}",
            status_code=404,
        )

    # 6. Compute HMAC signature
    now = utcnow()
    sig = compute_signoff_hmac(key, handover_id, version, hv.hash, user.id, now.isoformat())

    # 7. Upsert Signoff record for this user and version
    existing = session.exec(
        select(Signoff).where(
            Signoff.handover_id == handover_id,
            Signoff.version == version,
            Signoff.user_id == user.id,
        )
    ).first()

    if existing:
        existing.comment = comment
        existing.signature = sig
        existing.signed_at = now
        existing.role = signer_role
        session.add(existing)
        signoff_rec = existing
    else:
        signoff_rec = Signoff(
            handover_id=handover_id,
            version=version,
            user_id=user.id,
            role=signer_role,
            signature=sig,
            signed_at=now,
            comment=comment,
        )
        session.add(signoff_rec)

    session.flush()

    # 8. Check if BOTH roles have signed this version
    all_signoffs = session.exec(
        select(Signoff).where(
            Signoff.handover_id == handover_id,
            Signoff.version == version,
        )
    ).all()

    roles_signed = {s.role for s in all_signoffs}
    both_signed = ("outgoing" in roles_signed) and ("lead" in roles_signed)

    if both_signed:
        handover.status = "signed"
        handover.updated_at = utcnow()
        session.add(handover)
        logger.info(
            "Handover %s version %d fully SIGNED by both outgoing and lead",
            handover_id,
            version,
        )

    # Write audit log
    audit(
        session,
        actor_id=user.id,
        action="signoff_completed",
        target_type="signoff",
        target_id=signoff_rec.id,
        payload={
            "handover_id": handover_id,
            "version": version,
            "role": signer_role,
            "signature": sig,
            "both_signed": both_signed,
        },
    )

    session.commit()
    session.refresh(signoff_rec)
    session.refresh(handover)

    return {
        "id": signoff_rec.id,
        "handover_id": handover_id,
        "version": version,
        "user_id": user.id,
        "role": signer_role,
        "signature": sig,
        "signed_at": signoff_rec.signed_at.isoformat(),
        "comment": comment,
        "both_signed": both_signed,
        "handover_status": handover.status,
    }


def verify_handover(
    session: Session,
    handover_id: str,
    secret_key: str | None = None,
) -> dict[str, Any]:
    """Verify cryptographic integrity of version hash chain and all sign-off signatures."""
    key = secret_key or get_settings().secret_key
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    # 1. Verify HandoverVersion hash chain
    versions = session.exec(
        select(HandoverVersion)
        .where(HandoverVersion.handover_id == handover_id)
        .order_by(HandoverVersion.version.asc())
    ).all()

    chain_valid = True
    errors: list[str] = []
    prev_hash = ""

    version_hash_map: dict[int, str] = {}
    for v in versions:
        version_hash_map[v.version] = v.hash
        # Check chaining pointer
        if v.prev_hash != prev_hash:
            chain_valid = False
            errors.append(
                f"Version {v.version} prev_hash mismatch (expected '{prev_hash}', got '{v.prev_hash}')"
            )

        # Re-compute hash from snapshot content
        recalc_hash = compute_version_hash(prev_hash, v.snapshot or {})
        if recalc_hash != v.hash:
            chain_valid = False
            errors.append(
                f"Version {v.version} snapshot tampered: recalculation failed "
                f"(expected {v.hash}, got {recalc_hash})"
            )

        prev_hash = v.hash

    # 2. Verify all signatures on this handover
    signoffs = session.exec(
        select(Signoff).where(Signoff.handover_id == handover_id).order_by(Signoff.signed_at.asc())
    ).all()

    signatures_valid = True
    for s in signoffs:
        v_hash = version_hash_map.get(s.version)
        if not v_hash:
            signatures_valid = False
            errors.append(f"Sign-off {s.id} references non-existent version {s.version}")
            continue

        expected_sig = compute_signoff_hmac(
            key,
            handover_id,
            s.version,
            v_hash,
            s.user_id,
            s.signed_at.isoformat(),
        )
        if not hmac.compare_digest(expected_sig, s.signature):
            signatures_valid = False
            errors.append(f"Invalid cryptographic signature for user {s.user_id} on version {s.version}")

    tamper_detected = not chain_valid or not signatures_valid

    return {
        "chain_valid": chain_valid,
        "signatures_valid": signatures_valid,
        "details": {
            "handover_id": handover_id,
            "versions_checked": len(versions),
            "signatures_checked": len(signoffs),
            "tamper_detected": tamper_detected,
            "errors": errors,
        },
    }
