"""RelayOps data models (SQLModel).

Every table (except audit_log and schema_version) uses a 26-char ULID primary key
and timezone-aware UTC created_at/updated_at timestamps.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, UniqueConstraint
from sqlmodel import Field, SQLModel

from .db import new_ulid, utcnow


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    email: str = Field(unique=True, index=True)
    name: str
    password_hash: str
    role: str = Field(default="successor")  # lead, outgoing, successor, contractor, auditor
    clearance: int = Field(default=0)  # 0 public, 1 internal, 2 confidential, 3 restricted
    is_active: bool = Field(default=True)


class Project(SQLModel, table=True):
    __tablename__ = "project"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    name: str
    slug: str = Field(unique=True, index=True)
    description: str = Field(default="")
    repo_url: str | None = Field(default=None)
    status: str = Field(default="active")


class ProjectMember(SQLModel, table=True):
    __tablename__ = "project_member"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    project_id: str = Field(foreign_key="project.id", index=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    project_role: str = Field(default="contributor")


class Source(SQLModel, table=True):
    __tablename__ = "source"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    project_id: str = Field(foreign_key="project.id", index=True)
    type: str  # github | jira_json | slack_json | markdown | pdf_text
    name: str
    config: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    status: str = Field(default="ready")
    last_synced_at: datetime | None = Field(default=None)
    stats: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)


class Artifact(SQLModel, table=True):
    __tablename__ = "artifact"
    __table_args__ = (
        UniqueConstraint("project_id", "kind", "external_id", name="uq_artifact_project_kind_external"),
    )

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    project_id: str = Field(foreign_key="project.id", index=True)
    source_id: str = Field(foreign_key="source.id", index=True)
    kind: str  # commit | pull_request | issue | chat_thread | adr_doc | meeting_note | code_file | branch
    external_id: str = Field(index=True)
    source_uri: str
    title: str
    body_redacted: str
    body_hash: str
    author_alias: str
    author_entity_id: str | None = Field(default=None, foreign_key="entity.id", index=True)
    valid_time: datetime  # when it happened in reality
    transaction_time: datetime = Field(default_factory=utcnow)  # when ingested into system
    sensitivity: int = Field(default=1)  # 0 public, 1 internal, 2 confidential, 3 restricted
    acl_tags: list[str] = Field(default_factory=list, sa_type=JSON)
    authority: float = Field(default=1.0)
    meta: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    redaction_count: int = Field(default=0)


class RedactionEvent(SQLModel, table=True):
    __tablename__ = "redaction_event"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    artifact_id: str = Field(foreign_key="artifact.id", index=True)
    rule: str
    count: int = Field(default=1)
    sample_masked: str  # audit of what was scrubbed, never stores originals


class Entity(SQLModel, table=True):
    __tablename__ = "entity"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    project_id: str = Field(foreign_key="project.id", index=True)
    type: str  # person | module | service | external_api
    canonical_name: str
    aliases: list[str] = Field(default_factory=list, sa_type=JSON)
    meta: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)


class Node(SQLModel, table=True):
    __tablename__ = "node"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    project_id: str = Field(foreign_key="project.id", index=True)
    type: str  # decision | blocker | module | person | commit | pr | issue | thread | doc | risk | runbook
    key: str = Field(index=True)
    label: str
    props: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    valid_from: datetime
    valid_to: datetime | None = Field(default=None)
    tx_from: datetime = Field(default_factory=utcnow)
    tx_to: datetime | None = Field(default=None)
    authority: float = Field(default=1.0)
    artifact_id: str | None = Field(default=None, foreign_key="artifact.id", index=True)


class Edge(SQLModel, table=True):
    __tablename__ = "edge"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    project_id: str = Field(foreign_key="project.id", index=True)
    src_node_id: str = Field(foreign_key="node.id", index=True)
    dst_node_id: str = Field(foreign_key="node.id", index=True)
    type: str  # SUPERSEDES | BLOCKS | OWNS | CONTRADICTS | DEPENDS_ON | REFERENCES | AUTHORED
    valid_from: datetime
    valid_to: datetime | None = Field(default=None)
    confidence: float = Field(default=1.0)
    evidence: list[dict[str, Any]] = Field(default_factory=list, sa_type=JSON)


class Handover(SQLModel, table=True):
    __tablename__ = "handover"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    project_id: str = Field(foreign_key="project.id", index=True)
    outgoing_user_id: str = Field(foreign_key="user.id", index=True)
    successor_user_id: str = Field(foreign_key="user.id", index=True)
    lead_user_id: str = Field(foreign_key="user.id", index=True)
    status: str = Field(default="draft")  # draft | reconstructing | in_review | signed | delivered
    current_version: int = Field(default=1)
    due_date: datetime | None = Field(default=None)
    notes: str = Field(default="")


class Claim(SQLModel, table=True):
    __tablename__ = "claim"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    project_id: str | None = Field(default=None, foreign_key="project.id", index=True, nullable=True)
    handover_id: str | None = Field(default=None, foreign_key="handover.id", index=True, nullable=True)
    section: str = Field(default="general")
    # architecture_decision | ownership | blocker | runbook | risk
    # dependency | open_work | contact | credential_ref
    kind: str
    text: str
    status: str = Field(default="draft")  # draft | accepted | edited | rejected | needs_review
    confidence: float = Field(default=1.0)
    sensitivity: int = Field(default=1)
    evidence: list[dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    origin: str = Field(default="llm")  # llm | rule | human
    edited_by: str | None = Field(default=None)
    rejected_reason: str | None = Field(default=None)
    order_index: int = Field(default=0)
    parent_claim_id: str | None = Field(default=None, foreign_key="claim.id")


class Ambiguity(SQLModel, table=True):
    __tablename__ = "ambiguity"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    project_id: str | None = Field(default=None, foreign_key="project.id", index=True, nullable=True)
    handover_id: str | None = Field(default=None, foreign_key="handover.id", index=True, nullable=True)
    # missing_doc | conflict | orphan_branch | unclosed_thread | stale_config
    # low_evidence | undocumented_module
    type: str
    severity: str  # low | med | high
    title: str
    description: str
    artifact_ids: list[str] = Field(default_factory=list, sa_type=JSON)
    status: str = Field(default="open")  # open | resolved | waived
    resolution_note: str | None = Field(default=None)
    resolved_by: str | None = Field(default=None)


class HandoverVersion(SQLModel, table=True):
    __tablename__ = "handover_version"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    handover_id: str = Field(foreign_key="handover.id", index=True)
    version: int
    snapshot: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    prev_hash: str = Field(default="")
    hash: str
    created_by: str | None = Field(default=None)
    reason: str = Field(default="")


class Signoff(SQLModel, table=True):
    __tablename__ = "signoff"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    handover_id: str = Field(foreign_key="handover.id", index=True)
    version: int
    user_id: str = Field(foreign_key="user.id", index=True)
    role: str  # outgoing | lead
    signature: str  # HMAC
    signed_at: datetime = Field(default_factory=utcnow)
    comment: str = Field(default="")


class PlanItem(SQLModel, table=True):
    __tablename__ = "plan_item"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    handover_id: str = Field(foreign_key="handover.id", index=True)
    day_bucket: str  # d1_7 | d8_14 | d15_30
    title: str
    description: str = Field(default="")
    priority: str = Field(default="medium")
    claim_ids: list[str] = Field(default_factory=list, sa_type=JSON)
    status: str = Field(default="todo")  # todo | doing | done
    assignee: str | None = Field(default=None)


class Receipt(SQLModel, table=True):
    __tablename__ = "receipt"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    handover_id: str = Field(foreign_key="handover.id", index=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    section: str
    acknowledged_at: datetime = Field(default_factory=utcnow)
    comprehension_note: str | None = Field(default=None)


class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_session"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    handover_id: str = Field(foreign_key="handover.id", index=True)
    user_id: str = Field(foreign_key="user.id", index=True)


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_message"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    session_id: str = Field(foreign_key="chat_session.id", index=True)
    role: str  # user | assistant | system
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    refused: bool = Field(default=False)
    feedback: str | None = Field(default=None)  # "up" | "down"


class Job(SQLModel, table=True):
    __tablename__ = "job"

    id: str = Field(default_factory=new_ulid, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    project_id: str = Field(foreign_key="project.id", index=True)
    handover_id: str | None = Field(default=None, foreign_key="handover.id", index=True)
    kind: str
    status: str = Field(default="queued")  # queued | running | done | failed
    progress: int = Field(default=0)
    stage: str = Field(default="")
    log: list[dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    error: str | None = Field(default=None)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    seq: int | None = Field(default=None, primary_key=True, sa_column_kwargs={"autoincrement": True})
    created_at: datetime = Field(default_factory=utcnow)
    actor_id: str | None = Field(default=None, index=True)
    action: str = Field(index=True)
    target_type: str = Field(index=True)
    target_id: str | None = Field(default=None, index=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    prev_hash: str = Field(default="")
    hash: str = Field(default="")


class SchemaVersion(SQLModel, table=True):
    __tablename__ = "schema_version"

    version: int = Field(primary_key=True)
    applied_at: datetime = Field(default_factory=utcnow)
    description: str = Field(default="")


class LLMCache(SQLModel, table=True):
    __tablename__ = "llm_cache"

    key: str = Field(primary_key=True)
    task: str = Field(default="")
    response: str = Field(default="")
    meta: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    created_at: datetime = Field(default_factory=utcnow)
