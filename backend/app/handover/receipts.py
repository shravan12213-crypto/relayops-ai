"""Successor comprehension tracking and section-by-section receipt acknowledgements."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import audit, utcnow
from app.errors import AppError
from app.models import Claim, Handover, Receipt, User

logger = logging.getLogger("relayops.handover.receipts")


class ReceiptInput(BaseModel):
    section: str
    comprehension_note: str | None = None


def acknowledge_section_receipt(
    session: Session,
    handover_id: str,
    user: User,
    data: ReceiptInput,
) -> dict[str, Any]:
    """Acknowledge reading and comprehension of a specific handover section."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    clean_section = data.section.strip().lower()
    if not clean_section:
        raise AppError("VALIDATION_ERROR", "Section name cannot be empty", status_code=422)

    existing = session.exec(
        select(Receipt).where(
            Receipt.handover_id == handover_id,
            Receipt.user_id == user.id,
            Receipt.section == clean_section,
        )
    ).first()

    now = utcnow()
    if existing:
        existing.acknowledged_at = now
        existing.comprehension_note = data.comprehension_note
        existing.updated_at = now
        session.add(existing)
        receipt = existing
    else:
        receipt = Receipt(
            handover_id=handover_id,
            user_id=user.id,
            section=clean_section,
            acknowledged_at=now,
            comprehension_note=data.comprehension_note,
        )
        session.add(receipt)

    # Audit log
    audit(
        session,
        actor_id=user.id,
        action="receipt_acknowledged",
        target_type="receipt",
        target_id=receipt.id,
        payload={
            "handover_id": handover_id,
            "section": clean_section,
            "has_note": bool(data.comprehension_note),
        },
    )

    session.commit()
    session.refresh(receipt)
    return receipt.model_dump()


def get_receipts_progress(
    session: Session,
    handover_id: str,
    user: User | None = None,
) -> dict[str, Any]:
    """Calculate comprehension progress percentage across unique handover sections."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    # Determine unique sections present in the handover claims
    claims = session.exec(select(Claim).where(Claim.handover_id == handover_id)).all()
    sections = {c.section.strip().lower() for c in claims if c.section}
    if not sections:
        sections = {"architecture", "runbooks", "operations"}

    # Fetch receipts (for successor if defined, otherwise all)
    query = select(Receipt).where(Receipt.handover_id == handover_id)
    if user and user.role == "successor":
        query = query.where(Receipt.user_id == user.id)

    receipts = session.exec(query).all()
    acknowledged_sections = {r.section.lower() for r in receipts}

    total_count = len(sections)
    ack_count = len(acknowledged_sections & sections)
    progress_pct = round((ack_count / total_count) * 100, 1) if total_count > 0 else 0.0

    return {
        "handover_id": handover_id,
        "total_sections": sorted(sections),
        "acknowledged_sections": sorted(acknowledged_sections),
        "total_sections_count": total_count,
        "acknowledged_count": ack_count,
        "progress_pct": min(progress_pct, 100.0),
        "receipts": [r.model_dump() for r in receipts],
    }
