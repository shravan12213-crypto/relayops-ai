"""Router for job status tracking, retry, and live Server-Sent Events (SSE)."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.auth import get_current_user
from app.db import get_session
from app.errors import AppError
from app.jobs import broker, run_handover_pipeline
from app.models import Job, User
from app.schemas import JobRead

logger = logging.getLogger("relayops.routers.jobs")
router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> JobRead:
    """Get the current status, progress, stage, and execution logs for a job."""
    job = session.get(Job, job_id)
    if not job:
        raise AppError("NOT_FOUND", "Job not found", status_code=404)
    return JobRead.model_validate(job)


@router.get("/jobs/{job_id}/events")
async def stream_job_events(
    job_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream real-time job progress events via Server-Sent Events (SSE)."""
    job = session.get(Job, job_id)
    if not job:
        raise AppError("NOT_FOUND", "Job not found", status_code=404)

    async def event_generator():
        # 1. Send existing logs first so reconnecting clients catch up instantly
        for entry in job.log or []:
            yield f"data: {json.dumps(entry)}\n\n"

        # If job is already terminal, finish stream
        if job.status in ("done", "failed"):
            return

        # 2. Subscribe to live broker updates
        q = await broker.subscribe(job_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    # Exit stream on completion or failure
                    if event.get("status") in ("done", "failed") or event.get("progress") >= 100:
                        break
                except TimeoutError:
                    # Keep-alive heartbeat comment
                    yield ": ping\n\n"
        finally:
            await broker.unsubscribe(job_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/jobs/{job_id}/retry", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def retry_job(
    job_id: str,
    from_stage: str | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> JobRead:
    """Retry a failed job starting from a specific stage (or the stage where it failed)."""
    job = session.get(Job, job_id)
    if not job:
        raise AppError("NOT_FOUND", "Job not found", status_code=404)

    if job.status not in ("failed", "done"):
        raise AppError("CONFLICT", f"Job is currently {job.status} and cannot be retried", status_code=409)

    retry_stage = from_stage or job.stage or "connect_check"
    job.status = "queued"
    job.error = None
    job.stage = retry_stage
    session.add(job)
    session.commit()
    session.refresh(job)

    if job.handover_id:
        background_tasks.add_task(
            run_handover_pipeline,
            job.id,
            job.handover_id,
            job.project_id,
            retry_stage,
        )

    return JobRead.model_validate(job)
