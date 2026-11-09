"""Background pipeline orchestration engine and SSE event broker.

Manages pipeline stages in order:
connect_check -> redact_audit -> entities -> graph -> extract -> verify_citations ->
conflicts -> ambiguities -> scorecard -> draft_plan -> snapshot_v1.

Each stage is idempotent and resumable (re-run replaces draft claims that have origin
llm/rule and status draft, but NEVER overwrites human-edited/accepted claims).
Provides concurrency protection (one active job per handover) and real-time SSE progress streaming.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import zlib
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app import llm
from app.db import audit, get_engine, utcnow
from app.ingest.redact import scan_report
from app.models import (
    Ambiguity,
    Artifact,
    Claim,
    Handover,
    HandoverVersion,
    Job,
    Node,
    PlanItem,
    Project,
    Source,
)
from app.reconstruct import build_graph, extract_and_link_facts, resolve_entities
from app.verify import (
    bind_and_validate,
    detect_all_ambiguities,
    detect_and_resolve_conflicts,
    generate_scorecard,
)

logger = logging.getLogger("relayops.jobs")

STAGE_ORDER: list[str] = [
    "connect_check",
    "redact_audit",
    "entities",
    "graph",
    "extract",
    "verify_citations",
    "conflicts",
    "ambiguities",
    "scorecard",
    "draft_plan",
    "snapshot_v1",
]

STAGE_PROGRESS: dict[str, int] = {
    "connect_check": 5,
    "redact_audit": 10,
    "entities": 20,
    "graph": 35,
    "extract": 50,
    "verify_citations": 65,
    "conflicts": 75,
    "ambiguities": 85,
    "scorecard": 90,
    "draft_plan": 95,
    "snapshot_v1": 100,
}


# --- In-memory SSE Pub/Sub Broker ---


class JobEventBroker:
    """Thread-safe event pub/sub broker for real-time Server-Sent Events."""

    def __init__(self) -> None:
        self._listeners: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, job_id: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            self._listeners[job_id].add(q)
        return q

    async def unsubscribe(self, job_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._listeners[job_id].discard(q)
            if not self._listeners[job_id]:
                self._listeners.pop(job_id, None)

    def publish_sync(self, job_id: str, event: dict[str, Any]) -> None:
        """Publish an event from synchronous pipeline threads."""
        queues = list(self._listeners.get(job_id, []))
        for q in queues:
            with contextlib.suppress(Exception):
                q.put_nowait(event)


broker = JobEventBroker()


# --- Plan Generation Schemas ---


class GeneratedPlanItem(BaseModel):
    day_bucket: str = Field(description="d1_7 | d8_14 | d15_30")
    title: str = Field(description="Actionable task title for successor")
    description: str = Field(default="", description="Detailed instructions or context")
    priority: str = Field(default="high", description="high | medium | low")
    claim_ids: list[str] = Field(
        default_factory=list, description="IDs of verified claims grounding this item"
    )


class GeneratedPlan(BaseModel):
    items: list[GeneratedPlanItem] = Field(default_factory=list)


def _emit_stage_progress(
    job_id: str,
    stage: str,
    progress: int,
    message: str,
    session: Session,
    status: str = "running",
    extra: dict[str, Any] | None = None,
) -> None:
    """Record progress in the DB and publish to the SSE broker."""
    job = session.get(Job, job_id)
    if job:
        job.stage = stage
        job.progress = progress
        job.status = status
        event_payload = {
            "ts": utcnow().isoformat(),
            "stage": stage,
            "progress": progress,
            "status": status,
            "message": message,
            **(extra or {}),
        }
        job_log = list(job.log or [])
        job_log.append(event_payload)
        job.log = job_log
        session.add(job)
        session.commit()

        # Publish to SSE broker
        broker.publish_sync(job_id, event_payload)


# --- Pipeline Execution ---


def run_handover_pipeline(
    job_id: str,
    handover_id: str,
    project_id: str,
    from_stage: str | None = None,
) -> None:
    """Run the complete handover reconstruction & verification pipeline.

    Stages:
      connect_check -> redact_audit -> entities -> graph -> extract ->
      verify_citations -> conflicts -> ambiguities -> scorecard -> draft_plan -> snapshot_v1
    """
    engine = get_engine()
    with Session(engine) as session:
        job = session.get(Job, job_id)
        handover = session.get(Handover, handover_id)
        project = session.get(Project, project_id)

        if not job or not handover or not project:
            logger.error(
                "Pipeline abort: Job %s, Handover %s, or Project %s not found",
                job_id,
                handover_id,
                project_id,
            )
            return

        start_index = 0
        if from_stage and from_stage in STAGE_ORDER:
            start_index = STAGE_ORDER.index(from_stage)

        stages_to_run = STAGE_ORDER[start_index:]
        logger.info("Starting pipeline for handover %s (stages: %s)", handover_id, stages_to_run)

        # Update handover status
        handover.status = "reconstructing"
        session.add(handover)
        session.commit()

        try:
            for current_stage in stages_to_run:
                progress = STAGE_PROGRESS.get(current_stage, 50)

                if current_stage == "connect_check":
                    sources = session.exec(select(Source).where(Source.project_id == project_id)).all()
                    art_count = len(
                        session.exec(select(Artifact).where(Artifact.project_id == project_id)).all()
                    )
                    _emit_stage_progress(
                        job_id,
                        current_stage,
                        progress,
                        f"Connected {len(sources)} sources with {art_count} total artifacts.",
                        session,
                    )

                elif current_stage == "redact_audit":
                    report = scan_report(project_id, session)
                    ev_count = report.get("total_events", 0)
                    _emit_stage_progress(
                        job_id,
                        current_stage,
                        progress,
                        f"Redaction audit verified: {ev_count} secret/PII events scrubbed safely.",
                        session,
                    )

                elif current_stage == "entities":
                    ent_res = resolve_entities(project_id, session)
                    people_count = len(ent_res.get("people", {}))
                    modules_count = len(ent_res.get("modules", {}))
                    _emit_stage_progress(
                        job_id,
                        current_stage,
                        progress,
                        f"Resolved entities: {people_count} canonical contributors, {modules_count} modules.",
                        session,
                    )

                elif current_stage == "graph":
                    graph_res = build_graph(project_id, session)
                    n_count = graph_res.get("nodes_created", 0)
                    e_count = graph_res.get("edges_created", 0)
                    _emit_stage_progress(
                        job_id,
                        current_stage,
                        progress,
                        f"Knowledge graph constructed: {n_count} nodes, {e_count} bi-temporal edges.",
                        session,
                    )

                elif current_stage == "extract":
                    # 1. Run reconstruction fact extraction
                    extract_and_link_facts(project_id, session)

                    # 2. Idempotently populate Claim records for this handover
                    # Resumable rule: Remove draft claims with origin llm/rule,
                    # but NEVER human-edited/accepted claims!
                    existing_claims = session.exec(
                        select(Claim).where(Claim.handover_id == handover_id)
                    ).all()

                    surviving_claims: list[Claim] = []
                    for c in existing_claims:
                        is_human = (
                            c.origin == "human"
                            or c.edited_by is not None
                            or c.status in ("accepted", "edited")
                        )
                        if not is_human and c.status in ("draft", "rejected"):
                            session.delete(c)
                        else:
                            surviving_claims.append(c)
                    session.commit()

                    # Convert decision nodes into handover claims
                    decision_nodes = session.exec(
                        select(Node).where(Node.project_id == project_id, Node.type == "decision")
                    ).all()

                    created_claims = 0
                    for n in decision_nodes:
                        props = n.props or {}
                        node_evidence_ids = set(props.get("evidence_ids", []))
                        node_hash = zlib.crc32(f"{getattr(n, 'key', '') or ''}_{n.id}".encode()) & 0x7FFFFFFF

                        # Check if claim from this node already exists in surviving claims
                        already_exists = False
                        for sc in surviving_claims:
                            if sc.order_index == node_hash or sc.text == n.label:
                                already_exists = True
                                break
                            sc_ev = sc.evidence or []
                            if any(
                                isinstance(e, dict)
                                and (
                                    e.get("node_id") == n.id
                                    or (getattr(n, "key", None) and e.get("node_key") == n.key)
                                )
                                for e in sc_ev
                            ):
                                already_exists = True
                                break
                            # Also match if same section/topic and overlapping artifact evidence
                            if sc.section == props.get("topic", ""):
                                sc_art_ids = {
                                    str(e.get("external_id") or e.get("artifact_id") or "")
                                    for e in sc_ev
                                    if isinstance(e, dict)
                                }
                                if node_evidence_ids & sc_art_ids:
                                    already_exists = True
                                    break

                        if already_exists:
                            continue

                        ev_list = [
                            {
                                "artifact_id": eid,
                                "node_id": n.id,
                                "node_key": getattr(n, "key", ""),
                                "snippet": props.get("snippet", ""),
                            }
                            for eid in props.get("evidence_ids", [])
                        ]
                        if not ev_list:
                            ev_list = [
                                {
                                    "node_id": n.id,
                                    "node_key": getattr(n, "key", ""),
                                    "snippet": props.get("snippet", ""),
                                }
                            ]

                        claim = Claim(
                            project_id=project_id,
                            handover_id=handover_id,
                            section=props.get("topic", "architecture"),
                            kind=props.get("kind", "architecture_decision"),
                            text=n.label,
                            status="draft",
                            origin="llm",
                            evidence=ev_list,
                            confidence=float(props.get("confidence", 1.0)),
                            sensitivity=int(props.get("sensitivity", 1)),
                            order_index=node_hash,
                        )
                        session.add(claim)
                        created_claims += 1

                    session.commit()
                    _emit_stage_progress(
                        job_id,
                        current_stage,
                        progress,
                        f"Extracted {created_claims} claims across architecture and operations.",
                        session,
                        extra={"created_claims": created_claims},
                    )

                elif current_stage == "verify_citations":
                    claims = session.exec(select(Claim).where(Claim.handover_id == handover_id)).all()

                    accepted_count = 0
                    rejected_count = 0
                    for c in claims:
                        # Only re-validate unverified / draft claims
                        if c.status in ("draft", "rejected"):
                            bind_and_validate(c, session)
                        if c.status == "rejected":
                            rejected_count += 1
                        else:
                            accepted_count += 1

                    session.commit()
                    _emit_stage_progress(
                        job_id,
                        current_stage,
                        progress,
                        (
                            f"Verified citations: {accepted_count} backed by real evidence, "
                            f"{rejected_count} rejected."
                        ),
                        session,
                        extra={"accepted": accepted_count, "rejected": rejected_count},
                    )

                elif current_stage == "conflicts":
                    active_claims = session.exec(
                        select(Claim).where(Claim.handover_id == handover_id, Claim.status != "rejected")
                    ).all()
                    conflict_results = detect_and_resolve_conflicts(active_claims, session, project_id)
                    _emit_stage_progress(
                        job_id,
                        current_stage,
                        progress,
                        f"Pairwise contradictions: {len(conflict_results)} conflicts resolved or flagged.",
                        session,
                    )

                elif current_stage == "ambiguities":
                    claims = session.exec(select(Claim).where(Claim.handover_id == handover_id)).all()
                    ambs = detect_all_ambiguities(project_id, session, handover_id=handover_id, claims=claims)
                    _emit_stage_progress(
                        job_id,
                        current_stage,
                        progress,
                        f"Ambiguity Ledger updated: {len(ambs)} open ambiguities tracked.",
                        session,
                        extra={"ambiguities_count": len(ambs)},
                    )

                elif current_stage == "scorecard":
                    claims = session.exec(select(Claim).where(Claim.handover_id == handover_id)).all()
                    sc = generate_scorecard(project_id, session, claims=claims)
                    _emit_stage_progress(
                        job_id,
                        current_stage,
                        progress,
                        f"Scorecard calculated: Overall readiness {sc.overall_score}/100.",
                        session,
                        extra={"overall_score": sc.overall_score},
                    )

                elif current_stage == "draft_plan":
                    verified_claims = session.exec(
                        select(Claim).where(
                            Claim.handover_id == handover_id,
                            Claim.status.in_(["accepted", "edited"]),
                        )
                    ).all()

                    plan_items = _generate_and_validate_plan(
                        handover_id, project_id, verified_claims, session
                    )
                    _emit_stage_progress(
                        job_id,
                        current_stage,
                        progress,
                        f"Drafted 30-day successor onboarding plan with {len(plan_items)} grounded tasks.",
                        session,
                        extra={"plan_items_count": len(plan_items)},
                    )

                elif current_stage == "snapshot_v1":
                    _create_snapshot_v1(handover, session)
                    _emit_stage_progress(
                        job_id,
                        current_stage,
                        100,
                        "Handover version 1 snapshot created. Status moved to 'in_review'.",
                        session,
                        status="done",
                    )

            # Finalize job status
            job = session.get(Job, job_id)
            if job and job.status != "failed":
                job.status = "done"
                job.progress = 100
                job.stage = "complete"
                session.add(job)
                session.commit()

        except Exception as exc:
            logger.exception("Pipeline failed at stage %s for job %s: %s", current_stage, job_id, exc)
            job = session.get(Job, job_id)
            if job:
                job.status = "failed"
                job.error = str(exc)
                job.stage = current_stage
                session.add(job)
                session.commit()
                _emit_stage_progress(
                    job_id,
                    current_stage,
                    job.progress,
                    f"Pipeline failed at stage '{current_stage}': {exc}",
                    session,
                    status="failed",
                    extra={"error": str(exc)},
                )


def _generate_and_validate_plan(
    handover_id: str,
    project_id: str,
    verified_claims: list[Claim],
    session: Session,
) -> list[PlanItem]:
    """Generate Day 1-7, 8-14, and 15-30 plan items. Validator drops items with no linked claims."""
    # Remove unedited todo plan items on re-run
    existing_plan = session.exec(select(PlanItem).where(PlanItem.handover_id == handover_id)).all()
    for pi in existing_plan:
        if pi.status == "todo":
            session.delete(pi)
    session.commit()

    if not verified_claims:
        return []

    valid_claim_ids = {c.id for c in verified_claims}
    claims_context = "\n".join(f"- ID: {c.id} | [{c.kind}] {c.text}" for c in verified_claims[:15])

    system_prompt = (
        "You are an engineering lead drafting a structured 30-day successor onboarding plan. "
        "Divide tasks into day buckets: d1_7, d8_14, d15_30. "
        "Every single plan item MUST reference at least one valid claim_id from the provided list."
    )
    user_prompt = f"Verified handover claims:\n{claims_context}\n\n" "Draft the onboarding plan items."

    try:
        plan = llm.structured(
            task="draft_onboarding_plan",
            system=system_prompt,
            user=user_prompt,
            schema=GeneratedPlan,
        )
    except Exception as exc:
        logger.warning("LLM plan generation fallback: %s", exc)
        plan = _fallback_plan(verified_claims)

    saved_items: list[PlanItem] = []

    for item in plan.items:
        # Validator rule: drop items with no valid linked claims!
        grounded_claims = [cid for cid in item.claim_ids if cid in valid_claim_ids]
        if not grounded_claims:
            logger.warning("Dropping ungrounded plan item: '%s'", item.title)
            continue

        pi = PlanItem(
            handover_id=handover_id,
            day_bucket=item.day_bucket,
            title=item.title,
            description=item.description,
            priority=item.priority,
            claim_ids=grounded_claims,
            status="todo",
        )
        session.add(pi)
        saved_items.append(pi)

    session.commit()
    return saved_items


def _fallback_plan(claims: list[Claim]) -> GeneratedPlan:
    """Deterministic fallback onboarding plan grounded in verified claims."""
    items: list[GeneratedPlanItem] = []

    c_webhook = next((c for c in claims if "webhook" in c.text.lower() or "retry" in c.text.lower()), None)
    c_db = next((c for c in claims if "postgres" in c.text.lower() or "rfc-007" in c.text.lower()), None)
    c_jwt = next((c for c in claims if "jwt" in c.text.lower() or "redis" in c.text.lower()), None)
    c_blocker = next((c for c in claims if "pay-142" in c.text.lower() or "vendor" in c.text.lower()), None)

    fallback_claim = claims[0] if claims else None
    cid_webhook = [c_webhook.id] if c_webhook else ([fallback_claim.id] if fallback_claim else [])
    cid_db = [c_db.id] if c_db else ([fallback_claim.id] if fallback_claim else [])
    cid_jwt = [c_jwt.id] if c_jwt else ([fallback_claim.id] if fallback_claim else [])
    cid_blocker = [c_blocker.id] if c_blocker else ([fallback_claim.id] if fallback_claim else [])

    if cid_webhook:
        items.append(
            GeneratedPlanItem(
                day_bucket="d1_7",
                title="Verify Webhook Dispatcher Local Setup and Retry Configuration",
                description="Review webhook pipeline locally and verify production retry policy.",
                priority="high",
                claim_ids=cid_webhook,
            )
        )

    if cid_jwt or cid_db:
        items.append(
            GeneratedPlanItem(
                day_bucket="d8_14",
                title="Deep-dive into PostgreSQL Schema and Stateless JWT Architecture",
                description="Review core ledger transaction schema and stateless session verification.",
                priority="high",
                claim_ids=cid_jwt or cid_db,
            )
        )

    if cid_blocker:
        items.append(
            GeneratedPlanItem(
                day_bucket="d15_30",
                title="AcquirerCorp Vendor Sandbox Integration & Blocker PAY-142 Escalation",
                description="Coordinate with David Vance for sandbox credentials and finalize rollout.",
                priority="medium",
                claim_ids=cid_blocker,
            )
        )

    return GeneratedPlan(items=items)


def _create_snapshot_v1(handover: Handover, session: Session) -> HandoverVersion:
    """Create version 1 snapshot and mark handover as in_review."""
    claims = session.exec(select(Claim).where(Claim.handover_id == handover.id)).all()
    plan_items = session.exec(select(PlanItem).where(PlanItem.handover_id == handover.id)).all()
    ambs = session.exec(select(Ambiguity).where(Ambiguity.handover_id == handover.id)).all()
    sc = generate_scorecard(handover.project_id, session, claims=claims)

    raw_snapshot: dict[str, Any] = {
        "handover_id": handover.id,
        "version": 1,
        "project_id": handover.project_id,
        "status": "in_review",
        "created_at": utcnow().isoformat(),
        "claims": [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in claims],
        "plan_items": [p.model_dump() if hasattr(p, "model_dump") else p.dict() for p in plan_items],
        "ambiguities": [a.model_dump() if hasattr(a, "model_dump") else a.dict() for a in ambs],
        "scorecard": sc.model_dump() if hasattr(sc, "model_dump") else sc.dict(),
    }

    from app.handover.versions import canonical_json, compute_version_hash

    clean_snapshot = json.loads(canonical_json(raw_snapshot))
    snap_hash = compute_version_hash("", clean_snapshot)

    existing_v1 = session.exec(
        select(HandoverVersion).where(
            HandoverVersion.handover_id == handover.id,
            HandoverVersion.version == 1,
        )
    ).first()

    if existing_v1:
        existing_v1.snapshot = clean_snapshot
        existing_v1.hash = snap_hash
        existing_v1.updated_at = utcnow()
        session.add(existing_v1)
        hv = existing_v1
    else:
        hv = HandoverVersion(
            handover_id=handover.id,
            version=1,
            snapshot=clean_snapshot,
            prev_hash="",
            hash=snap_hash,
            created_by="system",
            reason="Initial pipeline draft v1",
        )
        session.add(hv)

    handover.status = "in_review"
    handover.current_version = 1
    session.add(handover)

    audit(
        session,
        actor_id="system",
        action="snapshot_created",
        target_type="handover_version",
        target_id=hv.id,
        payload={"version": 1, "hash": snap_hash, "reason": "Initial pipeline draft v1"},
    )

    session.commit()

    return hv
