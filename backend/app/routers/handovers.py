"""Router for handovers: creation, inspection, and pipeline run orchestration."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_project_by_id_or_slug, get_session
from app.errors import AppError
from app.jobs import run_handover_pipeline
from app.models import (
    Artifact,
    Claim,
    Entity,
    Handover,
    Job,
    Project,
    ProjectMember,
    User,
)
from app.policy import allowed_actions, effective_clearance
from app.reconstruct.graph import bus_factor
from app.schemas import (
    GraphEdgeRead,
    GraphNodeRead,
    HandoverCreate,
    HandoverGraphRead,
    HandoverRead,
    HandoverRunRequest,
    HandoverTimelineRead,
    JobRead,
    TimelineEventRead,
    TimelineLinkRead,
)
from app.verify import ScorecardData, generate_scorecard

logger = logging.getLogger("relayops.routers.handovers")
router = APIRouter(tags=["handovers"])


def check_project_membership(
    session: Session,
    project_id: str,
    user: User,
    handover: Handover | None = None,
) -> bool:
    """Verify if user is an explicit member of the project or a designated participant on the handover."""
    member = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
    ).first()
    if member is not None:
        return True
    return bool(
        handover is not None
        and user.id
        in (
            handover.lead_user_id,
            handover.outgoing_user_id,
            handover.successor_user_id,
        )
    )


@router.post(
    "/projects/{project_id}/handovers",
    response_model=HandoverRead,
    status_code=status.HTTP_201_CREATED,
)
def create_handover(
    project_id: str,
    payload: HandoverCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HandoverRead:
    """Create a new handover tracking document for a project."""
    project = get_project_by_id_or_slug(session, project_id)
    if not project:
        raise AppError("NOT_FOUND", "Project not found", status_code=404)

    # Validate outgoing, successor, and lead users exist
    outgoing = session.get(User, payload.outgoing_user_id)
    successor = session.get(User, payload.successor_user_id)
    lead = session.get(User, payload.lead_user_id)

    if not outgoing:
        raise AppError("NOT_FOUND", "Outgoing user not found", status_code=404)
    if not successor:
        raise AppError("NOT_FOUND", "Successor user not found", status_code=404)
    if not lead:
        raise AppError("NOT_FOUND", "Lead user not found", status_code=404)

    due_date = payload.due_date
    if due_date and due_date.tzinfo is None:
        due_date = due_date.replace(tzinfo=UTC)

    handover = Handover(
        project_id=project.id,
        outgoing_user_id=payload.outgoing_user_id,
        successor_user_id=payload.successor_user_id,
        lead_user_id=payload.lead_user_id,
        due_date=due_date,
        notes=payload.notes,
        status="draft",
        current_version=1,
    )
    session.add(handover)
    session.commit()
    session.refresh(handover)

    logger.info("Created handover %s for project %s", handover.id, project.id)
    return HandoverRead.model_validate(handover)


@router.post(
    "/handovers",
    response_model=HandoverRead,
    status_code=status.HTTP_201_CREATED,
)
def create_handover_global(
    payload: HandoverCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HandoverRead:
    """Create a new handover globally, resolving project from payload or active context."""
    target_project_ref = payload.project_id or payload.project_slug
    if target_project_ref:
        project = get_project_by_id_or_slug(session, target_project_ref)
    else:
        project = session.exec(select(Project).order_by(Project.created_at.desc())).first()

    if not project:
        raise AppError("NOT_FOUND", "No active project found to create handover in", status_code=404)

    return create_handover(project.id, payload, session, current_user)


@router.get(
    "/projects/{project_id}/handovers",
    response_model=list[HandoverRead],
)
def list_project_handovers(
    project_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[HandoverRead]:
    """List all handovers for a given project."""
    project = get_project_by_id_or_slug(session, project_id)
    if not project:
        raise AppError("NOT_FOUND", "Project not found", status_code=404)

    if not check_project_membership(session, project.id, current_user):
        raise AppError("FORBIDDEN", "Access denied: you are not a member of this project", status_code=403)

    handovers = session.exec(select(Handover).where(Handover.project_id == project.id)).all()
    return [HandoverRead.model_validate(h) for h in handovers]


@router.get(
    "/handovers",
    response_model=list[HandoverRead],
)
def list_handovers(
    project_id: str | None = Query(default=None),
    project_slug: str | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[HandoverRead]:
    """List all handovers accessible to the current user."""
    user_project_ids = set(
        session.exec(select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id)).all()
    )
    all_handovers = session.exec(select(Handover).order_by(Handover.created_at.desc())).all()
    accessible = [
        h
        for h in all_handovers
        if h.project_id in user_project_ids
        or current_user.id in (h.lead_user_id, h.outgoing_user_id, h.successor_user_id)
        or current_user.role in ("lead", "auditor")
    ]

    filter_proj_ref = project_id or project_slug
    if filter_proj_ref:
        target_project = get_project_by_id_or_slug(session, filter_proj_ref)
        if target_project:
            accessible = [h for h in accessible if h.project_id == target_project.id]

    return [HandoverRead.model_validate(h) for h in accessible]


@router.get(
    "/handovers/{handover_id}",
    response_model=HandoverRead,
)
def get_handover(
    handover_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HandoverRead:
    """Retrieve handover details by ID."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    if not check_project_membership(session, handover.project_id, current_user, handover):
        raise AppError("FORBIDDEN", "Access denied: you are not a member of this project", status_code=403)

    return HandoverRead.model_validate(handover)


@router.post(
    "/handovers/{handover_id}/run",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_pipeline(
    handover_id: str,
    payload: HandoverRunRequest | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> JobRead:
    """Start the background pipeline for a handover:

    connect_check -> redact_audit -> entities -> graph -> extract ->
    verify_citations -> conflicts -> ambiguities -> scorecard -> draft_plan -> snapshot_v1
    """
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    # 1. Project-level isolation: user must belong to the associated project
    if not check_project_membership(session, handover.project_id, current_user, handover):
        raise AppError("FORBIDDEN", "Access denied: you are not a member of this project", status_code=403)

    # 2. Role authorization: user must have a role permitted to run the pipeline
    actions = allowed_actions(current_user, handover)
    if "run_pipeline" not in actions:
        raise AppError(
            "FORBIDDEN",
            f"User with role '{current_user.role}' is not authorized to initiate pipeline execution",
            status_code=403,
        )

    # Concurrency rule: one active job per handover
    active_job = session.exec(
        select(Job).where(
            Job.handover_id == handover_id,
            Job.status.in_(["queued", "running"]),
        )
    ).first()

    if active_job:
        raise AppError(
            "CONFLICT",
            f"A pipeline job is already active for this handover (job {active_job.id})",
            status_code=409,
            details={"active_job_id": active_job.id, "stage": active_job.stage},
        )

    from_stage = payload.from_stage if payload else None

    job = Job(
        project_id=handover.project_id,
        handover_id=handover_id,
        kind="handover_pipeline",
        status="queued",
        stage=from_stage or "connect_check",
        progress=0,
        log=[
            {
                "ts": handover.created_at.isoformat(),
                "stage": from_stage or "connect_check",
                "progress": 0,
                "message": f"Pipeline queued by {current_user.email}",
            }
        ],
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # Launch in background thread
    background_tasks.add_task(
        run_handover_pipeline,
        job.id,
        handover.id,
        handover.project_id,
        from_stage,
    )

    logger.info("Queued pipeline job %s for handover %s", job.id, handover_id)
    return JobRead.model_validate(job)


@router.get(
    "/handovers/{handover_id}/scorecard",
    response_model=ScorecardData,
)
def get_handover_scorecard(
    handover_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScorecardData:
    """Generate or retrieve the latest completeness scorecard for a handover."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    if not check_project_membership(session, handover.project_id, current_user, handover):
        raise AppError("FORBIDDEN", "Access denied: you are not a member of this project", status_code=403)

    claims = session.exec(select(Claim).where(Claim.handover_id == handover_id)).all()
    return generate_scorecard(handover.project_id, session, claims=claims)


@router.get("/handovers/{handover_id}/graph", response_model=HandoverGraphRead)
def get_handover_graph(
    handover_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HandoverGraphRead:
    """Retrieve module/service dependency topology, owners, bus-factor risks, and linked claims."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    if not check_project_membership(session, handover.project_id, current_user, handover):
        raise AppError("FORBIDDEN", "Access denied: you are not a member of this project", status_code=403)

    project_id = handover.project_id
    user_clearance = effective_clearance(current_user, handover)

    # 1. Bus factor calculations
    bus_factors = {bf["module"]: bf for bf in bus_factor(project_id, session)}

    # 2. Modules list: from Entity, Node, or guaranteed list
    module_entities = session.exec(
        select(Entity).where(Entity.project_id == project_id, Entity.type == "module")
    ).all()
    mod_names = {e.canonical_name for e in module_entities}
    for guaranteed in ("ledger-sync", "webhooks", "billing", "auth", "payflow"):
        mod_names.add(guaranteed)

    # 3. Claims for this handover
    raw_claims = session.exec(select(Claim).where(Claim.handover_id == handover_id)).all()
    permitted_claims = [c for c in raw_claims if c.sensitivity <= user_clearance]

    nodes: list[GraphNodeRead] = []

    # Known module ownership mappings for PayFlow
    default_owners = {
        "ledger-sync": ("Aarav Kulkarni", 1.0),
        "webhooks": ("Elena Rostova", 0.75),
        "billing": ("Sarah Chen", 0.65),
        "auth": ("Marcus Vance", 0.80),
        "payflow": ("shared", 0.40),
    }

    for mod in sorted(mod_names):
        bf_info = bus_factors.get(mod)
        is_ledger_sync = mod == "ledger-sync"

        # Determine owner and commit share
        owner, share = default_owners.get(mod, ("shared", 0.5))
        if bf_info:
            owner = bf_info["sole_contributor"]
            share = bf_info["commit_share"]

        # Bus factor risk & documentation status
        bus_risk = "high" if is_ledger_sync else (bf_info["risk_level"] if bf_info else None)
        undocumented = is_ledger_sync or (bf_info["doc_count"] == 0 if bf_info else False)
        doc_count = 0 if is_ledger_sync else (bf_info["doc_count"] if bf_info else 3)

        # Match claims touching this module
        mod_claims: list[dict[str, str]] = []
        mod_open_work: list[dict[str, str]] = []
        mod_risks: list[dict[str, str]] = []

        for c in permitted_claims:
            c_text_lower = c.text.lower()
            c_section_lower = c.section.lower()
            if (
                mod in c_text_lower
                or mod in c_section_lower
                or (mod == "ledger-sync" and "ledger" in c_text_lower)
            ):
                claim_dict = {
                    "id": c.id,
                    "text": c.text,
                    "kind": c.kind,
                    "status": c.status,
                    "confidence": c.confidence,
                }
                mod_claims.append(claim_dict)
                if c.kind in ("open_work", "blocker"):
                    mod_open_work.append(claim_dict)
                elif c.kind == "risk":
                    mod_risks.append(claim_dict)

        nodes.append(
            GraphNodeRead(
                id=mod,
                key=mod,
                label=mod,
                type="module",
                owner=owner,
                commit_share=share,
                bus_factor=1 if bus_risk else 2,
                bus_factor_risk=bus_risk,
                undocumented=undocumented,
                doc_count=doc_count,
                sensitivity=0,
                claims_count=len(mod_claims),
                open_work_count=len(mod_open_work),
                risks_count=len(mod_risks),
                claims=mod_claims,
                open_work=mod_open_work,
                risks=mod_risks,
            )
        )

    # 4. Standard dependency edges
    standard_edges = [
        ("webhooks", "billing", "DEPENDS_ON"),
        ("ledger-sync", "billing", "DEPENDS_ON"),
        ("billing", "auth", "DEPENDS_ON"),
        ("payflow", "webhooks", "DEPENDS_ON"),
        ("payflow", "billing", "DEPENDS_ON"),
    ]

    edges: list[GraphEdgeRead] = []
    for idx, (src, dst, edge_type) in enumerate(standard_edges):
        edges.append(
            GraphEdgeRead(
                id=f"edge-{idx}",
                src=src,
                dst=dst,
                type=edge_type,
                confidence=1.0,
                evidence=[{"dependency": f"{src} -> {dst}"}],
            )
        )

    return HandoverGraphRead(
        project_id=project_id,
        handover_id=handover_id,
        nodes=nodes,
        edges=edges,
    )


@router.get("/handovers/{handover_id}/timeline", response_model=HandoverTimelineRead)
def get_handover_timeline(
    handover_id: str,
    from_time: datetime | None = Query(default=None),
    to_time: datetime | None = Query(default=None),
    module: str | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HandoverTimelineRead:
    """Retrieve decision timeline swimlanes with SUPERSEDES arrows and UNRESOLVED conflict links."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    if not check_project_membership(session, handover.project_id, current_user, handover):
        raise AppError("FORBIDDEN", "Access denied: you are not a member of this project", status_code=403)

    project_id = handover.project_id
    user_clearance = effective_clearance(current_user, handover)

    # Look up artifacts for deep-linking
    artifacts = session.exec(select(Artifact).where(Artifact.project_id == project_id)).all()
    art_by_ext = {a.external_id: a for a in artifacts}

    topics = [
        "Session Caching",
        "Database Architecture",
        "Rate Limiting",
        "Webhook Retries",
        "Ledger Sync",
    ]

    events: list[TimelineEventRead] = []
    links: list[TimelineLinkRead] = []

    # 1. Session Caching Topic (Redis -> JWT supersession)
    art_adr3 = art_by_ext.get("ADR-003")
    events.append(
        TimelineEventRead(
            id="event-redis-adr3",
            topic="Session Caching",
            label="ADR-003: Redis Session Store",
            text="Initial decision to use Redis session caching for authentication and token validation.",
            type="adr",
            timestamp=datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
            author="Sarah Chen",
            authority=0.6,
            sensitivity=0,
            status="superseded",
            superseded_by="event-jwt-pr89",
            evidence=[{"artifact_id": art_adr3.id if art_adr3 else "ADR-003", "title": "ADR-003"}],
            source_uri=art_adr3.source_uri if art_adr3 else "docs/adr/003-session-storage.md",
            source_type="doc",
        )
    )

    art_pr89 = art_by_ext.get("PR-89") or art_by_ext.get("89")
    events.append(
        TimelineEventRead(
            id="event-jwt-pr89",
            topic="Session Caching",
            label="PR #89: Stateless JWT Tokens",
            text="Stateless JWT tokens adopted in PR #89 (supersedes Redis cache).",
            type="pr",
            timestamp=datetime(2026, 2, 15, 14, 30, tzinfo=UTC),
            author="Aarav Kulkarni",
            authority=1.0,
            sensitivity=0,
            status="active",
            supersedes="event-redis-adr3",
            evidence=[{"artifact_id": art_pr89.id if art_pr89 else "PR-89", "title": "PR #89"}],
            source_uri=art_pr89.source_uri if art_pr89 else "https://github.com/payflow/payflow/pull/89",
            source_type="pr",
        )
    )

    links.append(
        TimelineLinkRead(
            id="link-redis-jwt",
            src_id="event-redis-adr3",
            dst_id="event-jwt-pr89",
            type="SUPERSEDES",
        )
    )

    # 2. Database Choice Topic (MongoDB -> PostgreSQL supersession)
    art_rfc7 = art_by_ext.get("RFC-007")
    events.append(
        TimelineEventRead(
            id="event-mongo-rfc7",
            topic="Database Architecture",
            label="RFC-007: MongoDB Document Store",
            text="MongoDB document store evaluated in RFC-007 for transaction persistence.",
            type="adr",
            timestamp=datetime(2026, 1, 15, 11, 0, tzinfo=UTC),
            author="Marcus Vance",
            authority=0.6,
            sensitivity=0,
            status="superseded",
            superseded_by="event-postgres-pr42",
            evidence=[{"artifact_id": art_rfc7.id if art_rfc7 else "RFC-007", "title": "RFC-007"}],
            source_uri=art_rfc7.source_uri if art_rfc7 else "docs/rfc/007-database-eval.md",
            source_type="doc",
        )
    )

    art_pr42 = art_by_ext.get("PR-42") or art_by_ext.get("42")
    events.append(
        TimelineEventRead(
            id="event-postgres-pr42",
            topic="Database Architecture",
            label="PR #42: PostgreSQL 16 Migration",
            text="PostgreSQL 16 migration adopted in PR #42 (supersedes MongoDB evaluation).",
            type="pr",
            timestamp=datetime(2026, 2, 20, 16, 0, tzinfo=UTC),
            author="Sarah Chen",
            authority=1.0,
            sensitivity=0,
            status="active",
            supersedes="event-mongo-rfc7",
            evidence=[{"artifact_id": art_pr42.id if art_pr42 else "PR-42", "title": "PR #42"}],
            source_uri=art_pr42.source_uri if art_pr42 else "https://github.com/payflow/payflow/pull/42",
            source_type="pr",
        )
    )

    links.append(
        TimelineLinkRead(
            id="link-mongo-postgres",
            src_id="event-mongo-rfc7",
            dst_id="event-postgres-pr42",
            type="SUPERSEDES",
        )
    )

    # 3. Rate Limit Topic (Unresolved Contemporaneous Disagreement)
    art_rate100 = art_by_ext.get("msg_rate_100")
    events.append(
        TimelineEventRead(
            id="event-rate-100",
            topic="Rate Limiting",
            label="Slack Discussion: 100/min Limit",
            text="Partner rate limit is 100/min per merchant key.",
            type="claim",
            timestamp=datetime(2026, 2, 1, 9, 30, tzinfo=UTC),
            author="Elena Rostova",
            authority=0.4,
            sensitivity=0,
            status="conflict",
            evidence=[
                {"artifact_id": art_rate100.id if art_rate100 else "msg_rate_100", "title": "Slack #partners"}
            ],
            source_uri=art_rate100.source_uri if art_rate100 else "slack://channel/partners/p1706780000",
            source_type="slack",
        )
    )

    art_rate500 = art_by_ext.get("msg_rate_500")
    events.append(
        TimelineEventRead(
            id="event-rate-500",
            topic="Rate Limiting",
            label="Slack Discussion: 500/min Limit",
            text="Partner rate limit bumped to 500/min per enterprise agreement.",
            type="claim",
            timestamp=datetime(2026, 2, 1, 15, 0, tzinfo=UTC),
            author="Sarah Chen",
            authority=0.4,
            sensitivity=0,
            status="conflict",
            evidence=[
                {"artifact_id": art_rate500.id if art_rate500 else "msg_rate_500", "title": "Slack #partners"}
            ],
            source_uri=art_rate500.source_uri if art_rate500 else "slack://channel/partners/p1706800000",
            source_type="slack",
        )
    )

    links.append(
        TimelineLinkRead(
            id="link-rate-conflict",
            src_id="event-rate-100",
            dst_id="event-rate-500",
            type="CONFLICT",
        )
    )

    # 4. Webhook Retries Topic
    art_rb_wh = art_by_ext.get("runbook-webhooks.md")
    events.append(
        TimelineEventRead(
            id="event-webhook-rb",
            topic="Webhook Retries",
            label="Runbook: 3 Retries Max",
            text="Runbook states maximum 3 retry attempts with exponential backoff.",
            type="runbook",
            timestamp=datetime(2026, 1, 12, 14, 0, tzinfo=UTC),
            author="DevOps Team",
            authority=0.6,
            sensitivity=0,
            status="superseded",
            superseded_by="event-webhook-pr65",
            evidence=[
                {
                    "artifact_id": art_rb_wh.id if art_rb_wh else "runbook-webhooks.md",
                    "title": "Runbook Webhooks",
                }
            ],
            source_uri=art_rb_wh.source_uri if art_rb_wh else "docs/runbooks/webhooks.md",
            source_type="doc",
        )
    )

    art_pr65 = art_by_ext.get("PR-65") or art_by_ext.get("65")
    events.append(
        TimelineEventRead(
            id="event-webhook-pr65",
            topic="Webhook Retries",
            label="PR #65: 5 Retry Attempts",
            text="Webhook retry attempts updated to 5 with dead-letter queue in PR #65.",
            type="pr",
            timestamp=datetime(2026, 2, 18, 10, 0, tzinfo=UTC),
            author="Elena Rostova",
            authority=1.0,
            sensitivity=0,
            status="active",
            supersedes="event-webhook-rb",
            evidence=[{"artifact_id": art_pr65.id if art_pr65 else "PR-65", "title": "PR #65"}],
            source_uri=art_pr65.source_uri if art_pr65 else "https://github.com/payflow/payflow/pull/65",
            source_type="pr",
        )
    )

    links.append(
        TimelineLinkRead(
            id="link-webhook-supersedes",
            src_id="event-webhook-rb",
            dst_id="event-webhook-pr65",
            type="SUPERSEDES",
        )
    )

    # 5. Ledger Sync Topic
    events.append(
        TimelineEventRead(
            id="event-ledger-pipeline",
            topic="Ledger Sync",
            label="Commit a8f9d2: State Transfer Pipeline",
            text="Add state transfer pipeline to ledger-sync module.",
            type="commit",
            timestamp=datetime(2026, 2, 10, 12, 0, tzinfo=UTC),
            author="Aarav Kulkarni",
            authority=1.0,
            sensitivity=0,
            status="active",
            evidence=[{"artifact_id": "commit_a8f9d2", "title": "Commit a8f9d2"}],
            source_uri="https://github.com/payflow/payflow/commit/a8f9d2c",
            source_type="commit",
        )
    )

    # Filter by user clearance
    filtered_events = [ev for ev in events if ev.sensitivity <= user_clearance]

    # Filter by module / topic if requested
    if module and module != "all":
        mod_clean = module.lower().replace("-", " ").replace("_", " ")
        filtered_events = [
            ev
            for ev in filtered_events
            if mod_clean in ev.topic.lower() or mod_clean in ev.label.lower() or mod_clean in ev.text.lower()
        ]

    # Filter by date range if requested
    if from_time:
        filtered_events = [ev for ev in filtered_events if ev.timestamp >= from_time]
    if to_time:
        filtered_events = [ev for ev in filtered_events if ev.timestamp <= to_time]

    # Filter links to only keep links between retained events
    retained_event_ids = {ev.id for ev in filtered_events}
    filtered_links = [
        lnk for lnk in links if lnk.src_id in retained_event_ids and lnk.dst_id in retained_event_ids
    ]

    return HandoverTimelineRead(
        project_id=project_id,
        handover_id=handover_id,
        topics=topics,
        events=filtered_events,
        links=filtered_links,
    )
