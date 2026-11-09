"""30-Day onboarding plan operations: status tracking, assignments, and claim grounding."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.db import audit, utcnow
from app.errors import AppError
from app.models import Claim, Handover, PlanItem, User
from app.policy import effective_clearance

logger = logging.getLogger("relayops.handover.plan")


class PlanItemCreateInput(BaseModel):
    day_bucket: str = "d1_7"  # d1_7 | d8_14 | d15_30
    title: str
    description: str = ""
    priority: str = "medium"  # low | medium | high
    claim_ids: list[str] = Field(default_factory=list)
    assignee: str | None = None


class PlanItemUpdateInput(BaseModel):
    item_id: str | None = None
    day_bucket: str | None = None  # d1_7 | d8_14 | d15_30
    status: str | None = None  # todo | doing | done
    assignee: str | None = None
    title: str | None = None
    description: str | None = None
    priority: str | None = None


def get_plan(session: Session, handover_id: str, viewer: User | None = None) -> list[dict[str, Any]]:
    """Retrieve all onboarding plan items for a handover, embedding grounded claim summaries."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    eff_clearance = effective_clearance(viewer) if viewer else 3

    items = session.exec(
        select(PlanItem).where(PlanItem.handover_id == handover_id).order_by(PlanItem.day_bucket, PlanItem.id)
    ).all()

    # Fetch all relevant claims for efficient grounding lookup
    all_cids = {cid for item in items for cid in (item.claim_ids or [])}
    claims_map: dict[str, Claim] = {}
    if all_cids:
        claims = session.exec(select(Claim).where(Claim.id.in_(all_cids))).all()
        claims_map = {c.id: c for c in claims}

    result: list[dict[str, Any]] = []
    for item in items:
        data = item.model_dump()
        linked_claims = []
        for cid in item.claim_ids or []:
            c = claims_map.get(cid)
            if c:
                c_text = (
                    c.text
                    if eff_clearance >= c.sensitivity
                    else f"[Restricted: requires clearance {c.sensitivity}]"
                )
                linked_claims.append(
                    {
                        "id": c.id,
                        "text": c_text,
                        "section": c.section,
                        "status": c.status,
                        "kind": c.kind,
                    }
                )
        data["linked_claims"] = linked_claims
        result.append(data)

    return result


def create_plan_item(
    session: Session,
    handover_id: str,
    user: User,
    data: PlanItemCreateInput,
) -> dict[str, Any]:
    """Add a custom onboarding plan item to a handover."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    item = PlanItem(
        handover_id=handover_id,
        day_bucket=data.day_bucket,
        title=data.title,
        description=data.description,
        priority=data.priority,
        claim_ids=data.claim_ids,
        status="todo",
        assignee=data.assignee,
    )
    session.add(item)

    # Audit log
    audit(
        session,
        actor_id=user.id,
        action="plan_item_created",
        target_type="plan_item",
        target_id=item.id,
        payload={"handover_id": handover_id, "title": item.title, "day_bucket": item.day_bucket},
    )

    session.commit()
    session.refresh(item)
    return item.model_dump()


def update_plan_item(
    session: Session,
    handover_id: str,
    item_id: str,
    user: User,
    data: PlanItemUpdateInput,
) -> dict[str, Any]:
    """Update status, assignment, or details of a plan item."""
    item = session.get(PlanItem, item_id)
    if not item or item.handover_id != handover_id:
        raise AppError("NOT_FOUND", "Plan item not found for this handover", status_code=404)

    if data.status is not None:
        if data.status not in ("todo", "doing", "done"):
            raise AppError("BAD_REQUEST", f"Invalid plan status '{data.status}'", status_code=400)
        item.status = data.status

    if data.day_bucket is not None:
        if data.day_bucket not in ("d1_7", "d8_14", "d15_30"):
            raise AppError("BAD_REQUEST", f"Invalid day_bucket '{data.day_bucket}'", status_code=400)
        item.day_bucket = data.day_bucket

    if data.assignee is not None:
        item.assignee = data.assignee
    if data.title is not None:
        item.title = data.title
    if data.description is not None:
        item.description = data.description
    if data.priority is not None:
        item.priority = data.priority

    item.updated_at = utcnow()
    session.add(item)

    # Audit log
    audit(
        session,
        actor_id=user.id,
        action="plan_item_updated",
        target_type="plan_item",
        target_id=item.id,
        payload={"handover_id": handover_id, "new_status": item.status, "assignee": item.assignee},
    )

    session.commit()
    session.refresh(item)
    return item.model_dump()
