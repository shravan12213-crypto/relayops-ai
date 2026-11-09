"""Router for successor portal: role-scoped views, onboarding plan,
comprehension receipts, copilot Q&A, and exports.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import audit, get_session, utcnow
from app.errors import AppError
from app.handover.copilot import ask_copilot
from app.handover.export import export_handover
from app.handover.plan import (
    PlanItemCreateInput,
    PlanItemUpdateInput,
    create_plan_item,
    get_plan,
    update_plan_item,
)
from app.handover.receipts import (
    ReceiptInput,
    acknowledge_section_receipt,
    get_receipts_progress,
)
from app.handover.views import (
    build_handover_view,
    deliver_handover,
)
from app.models import Ambiguity, ChatMessage, ChatSession, Handover, User
from app.schemas import (
    AmbiguityRead,
    ChatMessageRead,
    CopilotChatResponse,
    CopilotFeedbackInput,
    HandoverDeliverResponse,
    HandoverViewResponse,
    OpenQuestionInput,
    PlanItemRead,
    PlanItemWithClaimsRead,
    ReceiptRecordResponse,
    ReceiptsProgressResponse,
)

logger = logging.getLogger("relayops.routers.portal")
router = APIRouter(tags=["portal"])


class ChatQueryInput(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=50)


# ---------------------------------------------------------------------------
# 1. Role-Scoped View & Delivery Endpoints
# ---------------------------------------------------------------------------


@router.get("/handovers/{handover_id}/view", response_model=HandoverViewResponse)
def get_handover_view(
    handover_id: str,
    as_role: str | None = Query(default=None, alias="as"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HandoverViewResponse:
    """Retrieve successor-facing handover view from the latest signed snapshot."""
    res = build_handover_view(session, handover_id, current_user, as_role=as_role)
    return HandoverViewResponse.model_validate(res)


@router.post("/handovers/{handover_id}/deliver", response_model=HandoverDeliverResponse)
def deliver_handover_endpoint(
    handover_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HandoverDeliverResponse:
    """Mark signed handover as delivered. Restricted to project lead."""
    res = deliver_handover(session, handover_id, current_user)
    return HandoverDeliverResponse.model_validate(res)


# ---------------------------------------------------------------------------
# 2. 30-Day Plan Endpoints
# ---------------------------------------------------------------------------


@router.get("/handovers/{handover_id}/plan", response_model=list[PlanItemWithClaimsRead])
def list_plan_items(
    handover_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[PlanItemWithClaimsRead]:
    """Retrieve all plan items for a handover with embedded linked claim references."""
    items = get_plan(session, handover_id, current_user)
    return [PlanItemWithClaimsRead.model_validate(item) for item in items]


@router.post(
    "/handovers/{handover_id}/plan",
    response_model=PlanItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_custom_item(
    handover_id: str,
    payload: PlanItemCreateInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PlanItemRead:
    """Add a custom plan item."""
    res = create_plan_item(session, handover_id, current_user, payload)
    return PlanItemRead.model_validate(res)


@router.patch("/handovers/{handover_id}/plan/{item_id}", response_model=PlanItemRead)
def update_item(
    handover_id: str,
    item_id: str,
    payload: PlanItemUpdateInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PlanItemRead:
    """Update status, assignment, or details of a plan item."""
    res = update_plan_item(session, handover_id, item_id, current_user, payload)
    return PlanItemRead.model_validate(res)


@router.patch("/handovers/{handover_id}/plan", response_model=PlanItemRead)
def update_item_batch(
    handover_id: str,
    payload: PlanItemUpdateInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PlanItemRead:
    """Update status or assignment of a plan item specified in payload."""
    if not payload.item_id:
        raise AppError("VALIDATION_ERROR", "item_id is required in payload", status_code=422)
    res = update_plan_item(session, handover_id, payload.item_id, current_user, payload)
    return PlanItemRead.model_validate(res)


# ---------------------------------------------------------------------------
# 3. Comprehension Receipts Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/handovers/{handover_id}/receipts",
    response_model=ReceiptRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_receipt(
    handover_id: str,
    payload: ReceiptInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReceiptRecordResponse:
    """Acknowledge reading and comprehension of a specific handover section."""
    res = acknowledge_section_receipt(session, handover_id, current_user, payload)
    return ReceiptRecordResponse.model_validate(res)


@router.get("/handovers/{handover_id}/receipts", response_model=ReceiptsProgressResponse)
def get_receipts(
    handover_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReceiptsProgressResponse:
    """Retrieve comprehension receipts progress percentage."""
    res = get_receipts_progress(session, handover_id, current_user)
    return ReceiptsProgressResponse.model_validate(res)


# ---------------------------------------------------------------------------
# 4. Copilot Grounded Q&A Endpoint
# ---------------------------------------------------------------------------


@router.post("/handovers/{handover_id}/chat", response_model=CopilotChatResponse)
def chat_with_copilot(
    handover_id: str,
    payload: ChatQueryInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CopilotChatResponse:
    """Ask a question about the handover with SQL clearance firewall and citation validation."""
    res = ask_copilot(
        session,
        handover_id,
        current_user,
        payload.message,
        session_id=payload.session_id,
    )
    return CopilotChatResponse.model_validate(res)


@router.get("/handovers/{handover_id}/chat/messages", response_model=list[ChatMessageRead])
def get_chat_messages(
    handover_id: str,
    session_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[ChatMessageRead]:
    """Retrieve chat message history for this handover and user."""
    if session_id:
        chat_sess = session.exec(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.handover_id == handover_id,
            )
        ).first()
    else:
        chat_sess = session.exec(
            select(ChatSession)
            .where(
                ChatSession.handover_id == handover_id,
                ChatSession.user_id == current_user.id,
            )
            .order_by(ChatSession.updated_at.desc())
        ).first()

    if not chat_sess:
        return []

    messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_sess.id)
        .order_by(ChatMessage.created_at.asc())
    ).all()
    return [ChatMessageRead.model_validate(m) for m in messages]


@router.post("/handovers/{handover_id}/chat/messages/{message_id}/feedback")
def record_copilot_feedback(
    handover_id: str,
    message_id: str,
    payload: CopilotFeedbackInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Record user feedback (thumbs up/down) for a copilot message."""
    msg = session.get(ChatMessage, message_id)
    if not msg:
        raise AppError("NOT_FOUND", "Chat message not found", status_code=404)

    msg.feedback = payload.feedback
    msg.updated_at = utcnow()
    session.add(msg)

    audit(
        session,
        actor_id=current_user.id,
        action="copilot_feedback",
        target_type="chat_message",
        target_id=msg.id,
        payload={"handover_id": handover_id, "feedback": payload.feedback},
    )
    session.commit()
    return {"status": "ok", "message_id": msg.id, "feedback": payload.feedback}


# ---------------------------------------------------------------------------
# 5. Open Questions for Outgoing Owner Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/handovers/{handover_id}/questions",
    response_model=AmbiguityRead,
    status_code=status.HTTP_201_CREATED,
)
def create_handover_question(
    handover_id: str,
    payload: OpenQuestionInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AmbiguityRead:
    """Create an open question for the outgoing contributor."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    amb = Ambiguity(
        project_id=handover.project_id,
        handover_id=handover.id,
        type="open_question",
        severity="med",
        title=payload.title,
        description=payload.question,
        artifact_ids=payload.artifact_ids,
        status="open",
    )
    session.add(amb)
    session.commit()
    session.refresh(amb)

    audit(
        session,
        actor_id=current_user.id,
        action="open_question_created",
        target_type="ambiguity",
        target_id=amb.id,
        payload={"handover_id": handover.id, "title": amb.title, "question": amb.description},
    )
    return AmbiguityRead.model_validate(amb)


# ---------------------------------------------------------------------------
# 6. Handover Export Endpoint
# ---------------------------------------------------------------------------


@router.get("/handovers/{handover_id}/export")
def export_handover_endpoint(
    handover_id: str,
    format: str = Query(default="json", description="Export format: json, md, or html"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Export handover document in JSON, Markdown, or print-optimized HTML."""
    content, media_type = export_handover(session, handover_id, current_user, format=format)
    if isinstance(content, dict):
        return content
    return Response(content=content, media_type=media_type)
