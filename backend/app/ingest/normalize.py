"""Normalizer: transforms RawEvents into persistent Artifact records with authority and sensitivity rules."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlmodel import Session, select

from ..db import utcnow
from ..models import Artifact, RedactionEvent
from .base import RawEvent
from .redact import redact_text


def compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_authority(kind: str, meta: dict[str, Any]) -> float:
    """Source authority weights from specification:
    - Merged code/PR: 1.0
    - Unmerged / closed-unmerged PR: 0.5
    - Issue ticket: 0.8
    - ADR or meeting doc: 0.6
    - Chat: 0.4
    - Branch: 0.5
    """
    if kind == "commit":
        return 1.0

    if kind == "pull_request":
        status = str(meta.get("status", "merged")).lower()
        if status == "merged":
            return 1.0
        return 0.5

    if kind == "issue":
        return 0.8

    if kind in ("adr_doc", "meeting_note", "runbook", "doc"):
        return 0.6

    if kind == "chat_thread":
        return 0.4

    if kind == "branch":
        return 0.5

    return 0.5


def compute_sensitivity(acl_hint: str | None, meta: dict[str, Any]) -> int:
    """Sensitivity levels:
    - 0: public
    - 1: internal (default)
    - 2: confidential (leads-private, salary, vendor negotiations)
    - 3: restricted (legal, executive secrets)
    """
    if "sensitivity" in meta and isinstance(meta["sensitivity"], int):
        return meta["sensitivity"]

    hint = (acl_hint or "").lower().strip()
    if hint == "public":
        return 0
    if hint == "confidential":
        return 2
    if hint == "restricted":
        return 3
    return 1


def normalize_and_upsert_event(
    session: Session,
    *,
    project_id: str,
    source_id: str,
    event: RawEvent,
) -> Artifact:
    """Convert RawEvent into an Artifact, run redaction, and perform idempotent upsert."""
    # 1. Redact secrets and PII before storage
    body_redacted, redactions = redact_text(event.body)
    b_hash = compute_sha256(body_redacted)
    authority = compute_authority(event.kind, event.meta)
    sensitivity = compute_sensitivity(event.acl_hint, event.meta)
    now = utcnow()

    # 2. Check for existing artifact: UNIQUE(project_id, kind, external_id)
    existing = session.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.kind == event.kind,
            Artifact.external_id == event.external_id,
        )
    ).first()

    if existing:
        if existing.body_hash != b_hash:
            # Update and track prior revision in meta.history
            history = list(existing.meta.get("history", []))
            history.append(
                {
                    "body_hash": existing.body_hash,
                    "updated_at": existing.updated_at.isoformat(),
                    "title": existing.title,
                }
            )
            new_meta = dict(existing.meta)
            new_meta["history"] = history
            existing.meta = new_meta
            existing.title = event.title
            existing.body_redacted = body_redacted
            existing.body_hash = b_hash
            existing.authority = authority
            existing.sensitivity = sensitivity
            existing.source_uri = event.source_uri
            existing.valid_time = event.occurred_at
            existing.updated_at = now
            existing.redaction_count = len(redactions)
            session.add(existing)
        return existing

    # 3. Create new artifact
    artifact = Artifact(
        project_id=project_id,
        source_id=source_id,
        kind=event.kind,
        external_id=event.external_id,
        source_uri=event.source_uri,
        title=event.title,
        body_redacted=body_redacted,
        body_hash=b_hash,
        author_alias=event.author_alias,
        valid_time=event.occurred_at,
        transaction_time=now,
        sensitivity=sensitivity,
        authority=authority,
        meta=dict(event.meta),
        redaction_count=len(redactions),
        created_at=now,
        updated_at=now,
    )
    session.add(artifact)
    session.flush()

    # 4. Record redaction events
    for red in redactions:
        r_event = RedactionEvent(
            artifact_id=artifact.id,
            rule=red.get("rule", "unknown"),
            count=red.get("count", 1),
            sample_masked=red.get("sample_masked", "[REDACTED]"),
        )
        session.add(r_event)

    return artifact
