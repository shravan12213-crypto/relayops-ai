"""Pydantic schemas for API request and response envelopes."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
T = TypeVar("T")


class StatusResponse(BaseModel):
    ok: bool = True
    message: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_mode: str
    db: str


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    role: str
    clearance: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="successor")
    clearance: int = Field(default=0, ge=0, le=3)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Invalid email format")
        return clean


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Invalid email format")
        return clean


class LoginResponse(BaseModel):
    token: str
    user: UserRead


# --- Source and Ingestion Schemas ---


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str  # github | jira_json | slack_json | markdown | pdf_text
    config: dict[str, Any] = Field(default_factory=dict)


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    project_id: str
    type: str
    name: str
    config: dict[str, Any]
    status: str
    last_synced_at: datetime | None
    stats: dict[str, Any]


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    project_id: str
    handover_id: str | None
    kind: str
    status: str
    progress: int
    stage: str
    log: list[dict[str, Any]]
    error: str | None


class DemoLoadResponse(BaseModel):
    status: str
    project_id: str
    counts: dict[str, int]
    total_artifacts: int


# --- Handover and Plan Schemas ---


class HandoverCreate(BaseModel):
    outgoing_user_id: str = Field(min_length=1, max_length=50)
    successor_user_id: str = Field(min_length=1, max_length=50)
    lead_user_id: str = Field(min_length=1, max_length=50)
    due_date: datetime | None = None
    notes: str = Field(default="", max_length=5000)


class HandoverRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    project_id: str
    outgoing_user_id: str
    successor_user_id: str
    lead_user_id: str
    status: str
    current_version: int
    due_date: datetime | None
    notes: str


class HandoverRunRequest(BaseModel):
    from_stage: str | None = Field(default=None, max_length=50)


class PlanItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    handover_id: str
    day_bucket: str  # d1_7 | d8_14 | d15_30
    title: str
    description: str
    priority: str
    claim_ids: list[str]
    status: str
    assignee: str | None


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    project_id: str | None
    handover_id: str | None
    section: str
    kind: str
    text: str
    status: str
    confidence: float
    sensitivity: int
    evidence: list[dict[str, Any]]
    origin: str
    edited_by: str | None
    rejected_reason: str | None
    order_index: int
    parent_claim_id: str | None = None


class SnapshotCreateRequest(BaseModel):
    reason: str = Field(default="", max_length=1000)


class SignoffCreateRequest(BaseModel):
    version: int = Field(ge=1)
    comment: str = Field(default="", max_length=2000)


class SignoffRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    handover_id: str
    version: int
    user_id: str
    role: str
    signature: str
    signed_at: datetime
    comment: str


class HandoverVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    handover_id: str
    version: int
    prev_hash: str
    hash: str
    created_by: str | None
    reason: str
    created_at: datetime


class AmbiguityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    project_id: str | None
    handover_id: str | None
    type: str
    severity: str
    title: str
    description: str
    artifact_ids: list[str] = Field(default_factory=list)
    status: str
    resolution_note: str | None = None
    resolved_by: str | None = None


class ConflictItemRead(BaseModel):
    id: str
    handover_id: str
    subject: str
    title: str
    description: str
    status: str  # "unresolved" | "resolved" | "superseded"
    claim_a_id: str
    claim_a_text: str = ""
    claim_a_authority: float = 0.5
    claim_a_created_at: str | None = None
    claim_b_id: str
    claim_b_text: str = ""
    claim_b_authority: float = 0.5
    claim_b_created_at: str | None = None
    winner_claim_id: str | None = None
    loser_claim_id: str | None = None
    ambiguity_id: str | None = None
    chosen_resolution: str | None = None


class VersionDiffRead(BaseModel):
    from_version: int
    to_version: int
    claims: dict[str, Any]
    ambiguities: dict[str, Any]


class GraphNodeRead(BaseModel):
    id: str
    key: str
    label: str
    type: str  # module | service
    owner: str = "shared"
    commit_share: float = 0.0
    bus_factor: int = 1
    bus_factor_risk: str | None = None  # high | medium | None
    undocumented: bool = False
    doc_count: int = 0
    sensitivity: int = 0
    claims_count: int = 0
    open_work_count: int = 0
    risks_count: int = 0
    claims: list[dict[str, Any]] = Field(default_factory=list)
    open_work: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[dict[str, Any]] = Field(default_factory=list)


class GraphEdgeRead(BaseModel):
    id: str
    src: str
    dst: str
    type: str  # DEPENDS_ON | BLOCKS | OWNS
    confidence: float = 1.0
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class HandoverGraphRead(BaseModel):
    project_id: str
    handover_id: str
    nodes: list[GraphNodeRead]
    edges: list[GraphEdgeRead]


class TimelineEventRead(BaseModel):
    id: str
    topic: str
    label: str
    text: str
    type: str  # decision | pr | commit | adr | blocker | claim
    timestamp: datetime
    author: str | None = None
    authority: float = 1.0
    sensitivity: int = 0
    status: str = "active"  # active | superseded | conflict
    superseded_by: str | None = None
    supersedes: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    source_uri: str | None = None
    source_type: str | None = None


class TimelineLinkRead(BaseModel):
    id: str
    src_id: str
    dst_id: str
    type: str  # SUPERSEDES | CONFLICT


class HandoverTimelineRead(BaseModel):
    project_id: str
    handover_id: str
    topics: list[str]
    events: list[TimelineEventRead]
    links: list[TimelineLinkRead]


class HandoverVerificationDetails(BaseModel):
    handover_id: str
    versions_checked: int
    signatures_checked: int
    tamper_detected: bool
    errors: list[str] = Field(default_factory=list)


class HandoverVerificationRead(BaseModel):
    chain_valid: bool
    signatures_valid: bool
    details: HandoverVerificationDetails


class HandoverViewResponse(BaseModel):
    handover_id: str
    project_id: str
    version: int
    hash: str
    viewing_role: str
    effective_clearance: int
    status: str
    claims: list[dict[str, Any]]
    ambiguities: list[dict[str, Any]]
    plan_items: list[dict[str, Any]]
    scorecard: dict[str, Any]
    glossary: list[dict[str, Any]] | None = None
    signatures: list[dict[str, Any]] = Field(default_factory=list)
    audit_verification: dict[str, Any] | None = None
    redaction_summary: dict[str, Any] | None = None


class HandoverDeliverResponse(BaseModel):
    handover_id: str
    status: str
    delivered_at: str
    successor_user_id: str
    notification: str


class SignoffExecutionResponse(BaseModel):
    id: str
    handover_id: str
    version: int
    user_id: str
    role: str
    signature: str
    signed_at: str
    comment: str
    both_signed: bool
    handover_status: str


class LinkedClaimSummary(BaseModel):
    id: str
    text: str
    section: str
    status: str
    kind: str


class PlanItemWithClaimsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    handover_id: str
    day_bucket: str
    title: str
    description: str
    priority: str
    claim_ids: list[str]
    status: str
    assignee: str | None = None
    linked_claims: list[LinkedClaimSummary] = Field(default_factory=list)


class ReceiptRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    handover_id: str
    user_id: str
    section: str
    acknowledged_at: datetime
    comprehension_note: str | None = None


class ReceiptsProgressResponse(BaseModel):
    handover_id: str
    total_sections: list[str]
    acknowledged_sections: list[str]
    total_sections_count: int
    acknowledged_count: int
    progress_pct: float
    receipts: list[dict[str, Any]] = Field(default_factory=list)


class CopilotCitation(BaseModel):
    id: str
    snippet: str


class CopilotChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    citations: list[CopilotCitation] = Field(default_factory=list)
    can_answer: bool
    refused: bool


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    refused: bool = False
    feedback: str | None = None
    created_at: datetime


class CopilotFeedbackInput(BaseModel):
    feedback: str = Field(pattern="^(up|down)$")


class OpenQuestionInput(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    question: str = Field(min_length=5, max_length=4000)
    ambiguity_id: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)


# --- Redaction & Audit Schemas ---


class RedactionRuleSummary(BaseModel):
    rule: str
    count: int
    sample_masked: str


class RedactionAuditResponse(BaseModel):
    rules: list[RedactionRuleSummary]
    total_redactions: int


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    created_at: datetime
    actor_id: str | None = None
    action: str
    target_type: str
    target_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str | None = None
    hash: str


class AuditLogsPaginated(BaseModel):
    items: list[AuditLogRead]
    total: int
    page: int
    page_size: int


class AuditChainVerifyResponse(BaseModel):
    valid: bool
    entries_count: int
    tampered_seq: int | None = None
    error: str | None = None


class PolicyMatrixRule(BaseModel):
    role: str
    clearance: int
    clearance_name: str
    artifact_bodies_visible: bool
    claims_max_sensitivity: int
    can_signoff: bool
    can_deliver: bool
    can_view_audit: bool
    can_manage_members: bool
    notes: str


class PolicyMatrixResponse(BaseModel):
    roles: list[str]
    clearance_levels: list[dict[str, Any]]
    rules: list[PolicyMatrixRule]


class SensitivityBucket(BaseModel):
    level: int
    name: str
    artifacts_count: int
    claims_count: int
    total_count: int
    percentage: float


class SensitivityDistributionResponse(BaseModel):
    project_id: str
    total_artifacts: int
    total_claims: int
    buckets: list[SensitivityBucket]


class ProjectMemberRead(BaseModel):
    id: str
    project_id: str
    user_id: str
    project_role: str
    user_name: str
    user_email: str
    user_role: str
    user_clearance: int
    created_at: datetime


class ProjectMemberCreateInput(BaseModel):
    user_id: str
    project_role: str = "contributor"
    clearance: int | None = Field(default=None, ge=0, le=3)


class ProjectMemberUpdateInput(BaseModel):
    project_role: str | None = None
    clearance: int | None = Field(default=None, ge=0, le=3)


class SystemStatusResponse(BaseModel):
    llm_mode: str
    provider: str
    model: str
    environment: str
    database: str
    total_projects: int
    total_handovers: int


class ResetDemoResponse(BaseModel):
    status: str
    message: str
    project_id: str
    total_artifacts: int



class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    source_id: str
    kind: str
    external_id: str
    source_uri: str
    title: str
    body_redacted: str
    occurred_at: datetime
    meta: dict[str, Any] = Field(default_factory=dict)
    redaction_count: int = 0
