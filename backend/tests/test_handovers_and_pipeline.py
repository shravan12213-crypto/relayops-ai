"""Tests for P10: Pipeline orchestration, jobs, SSE, and handover life-cycle.

Validates:
- Handover creation via POST /api/v1/projects/{project_id}/handovers
- Pipeline execution across all 11 stages in order:
  connect_check -> redact_audit -> entities -> graph -> extract ->
  verify_citations -> conflicts -> ambiguities -> scorecard -> draft_plan -> snapshot_v1
- Concurrency protection: one active job per handover (409 Conflict)
- Resumability and idempotency: re-run replaces draft claims, preserves human edits
- Plan generator: Day 1-7, 8-14, 15-30 items grounded in verified claims (ungrounded dropped)
- Snapshot v1 creation with SHA-256 hash moving handover to in_review
- Job status polling and SSE event stream
- Acceptance: Full sequential flow (login -> demo load -> create handover -> run -> verify in_review).
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.jobs import run_handover_pipeline
from app.models import Claim, Handover, HandoverVersion, Job, PlanItem, Project, User
from app.routers.sources import execute_demo_load

# ---------------------------------------------------------------------------
# 1. Handover Creation Tests
# ---------------------------------------------------------------------------


def test_create_handover_api(client: TestClient, session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    users = session.exec(select(User)).all()
    by_role = {u.role: u for u in users}

    lead = by_role["lead"]
    outgoing = by_role["outgoing"]
    successor = by_role["successor"]

    # Login as lead
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": lead.email, "password": "password123"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "outgoing_user_id": outgoing.id,
        "successor_user_id": successor.id,
        "lead_user_id": lead.id,
        "due_date": "2026-11-30T00:00:00Z",
        "notes": "Payment webhooks handover before Aarav's departure.",
    }

    res = client.post(
        f"/api/v1/projects/{project.id}/handovers",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "draft"
    assert data["project_id"] == project.id
    assert data["outgoing_user_id"] == outgoing.id
    assert data["current_version"] == 1


# ---------------------------------------------------------------------------
# 2. Pipeline Execution & Stages Test
# ---------------------------------------------------------------------------


def test_full_pipeline_execution(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    users = session.exec(select(User)).all()
    by_role = {u.role: u for u in users}

    handover = Handover(
        project_id=project.id,
        outgoing_user_id=by_role["outgoing"].id,
        successor_user_id=by_role["successor"].id,
        lead_user_id=by_role["lead"].id,
        status="draft",
        notes="Automated pipeline test",
    )
    session.add(handover)
    session.commit()
    session.refresh(handover)

    job = Job(
        project_id=project.id,
        handover_id=handover.id,
        kind="handover_pipeline",
        status="queued",
        stage="connect_check",
        progress=0,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # Measure execution duration (< 60s requirement)
    t0 = time.perf_counter()
    run_handover_pipeline(job.id, handover.id, project.id)
    t1 = time.perf_counter()
    duration = t1 - t0

    assert duration < 60.0, f"Pipeline took too long: {duration:.2f}s"

    # Refresh DB records
    session.refresh(job)
    session.refresh(handover)

    assert job.status == "done"
    assert job.progress == 100
    assert job.stage == "complete"
    assert handover.status == "in_review"
    assert handover.current_version == 1

    # Verify HandoverVersion v1 snapshot was persisted
    v1 = session.exec(
        select(HandoverVersion).where(
            HandoverVersion.handover_id == handover.id,
            HandoverVersion.version == 1,
        )
    ).first()
    assert v1 is not None
    assert len(v1.hash) == 64  # SHA-256
    assert len(v1.snapshot["claims"]) > 0
    assert len(v1.snapshot["plan_items"]) > 0
    assert "scorecard" in v1.snapshot

    # Verify PlanItems exist and each has valid grounded claims
    plan_items = session.exec(select(PlanItem).where(PlanItem.handover_id == handover.id)).all()
    assert len(plan_items) >= 2
    buckets = {pi.day_bucket for pi in plan_items}
    assert "d1_7" in buckets

    # Every plan item must be grounded in valid claim IDs
    all_claims = session.exec(select(Claim).where(Claim.handover_id == handover.id)).all()
    claim_ids = {c.id for c in all_claims}
    for pi in plan_items:
        assert len(pi.claim_ids) > 0
        for cid in pi.claim_ids:
            assert cid in claim_ids


# ---------------------------------------------------------------------------
# 3. Concurrency Protection Test
# ---------------------------------------------------------------------------


def test_concurrency_protection(client: TestClient, session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    users = session.exec(select(User)).all()
    by_role = {u.role: u for u in users}

    handover = Handover(
        project_id=project.id,
        outgoing_user_id=by_role["outgoing"].id,
        successor_user_id=by_role["successor"].id,
        lead_user_id=by_role["lead"].id,
        status="draft",
    )
    session.add(handover)
    session.commit()
    session.refresh(handover)

    # Create an active running job
    active_job = Job(
        project_id=project.id,
        handover_id=handover.id,
        kind="handover_pipeline",
        status="running",
        stage="extract",
        progress=50,
    )
    session.add(active_job)
    session.commit()

    # Login as lead
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": by_role["lead"].email, "password": "password123"},
    )
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to start a second pipeline run concurrently
    run_res = client.post(f"/api/v1/handovers/{handover.id}/run", headers=headers)
    assert run_res.status_code == 409
    err = run_res.json()["error"]
    assert err["code"] == "CONFLICT"
    assert "already active" in err["message"]


# ---------------------------------------------------------------------------
# 4. Idempotent Rerun & Human Edit Preservation Test
# ---------------------------------------------------------------------------


def test_idempotent_rerun_preserves_human_edits(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    users = session.exec(select(User)).all()
    by_role = {u.role: u for u in users}

    handover = Handover(
        project_id=project.id,
        outgoing_user_id=by_role["outgoing"].id,
        successor_user_id=by_role["successor"].id,
        lead_user_id=by_role["lead"].id,
        status="draft",
    )
    session.add(handover)
    session.commit()
    session.refresh(handover)

    # Initial pipeline run
    job1 = Job(
        project_id=project.id,
        handover_id=handover.id,
        kind="handover_pipeline",
        status="queued",
    )
    session.add(job1)
    session.commit()
    run_handover_pipeline(job1.id, handover.id, project.id)

    # Find an extracted claim and simulate a human manual edit
    claims = session.exec(select(Claim).where(Claim.handover_id == handover.id)).all()
    assert len(claims) > 0
    edited_claim = claims[0]
    edited_claim.text = "CRITICAL HUMAN EDIT: Webhook signature verification verified by Aarav."
    edited_claim.status = "edited"
    edited_claim.origin = "human"
    edited_claim.edited_by = by_role["outgoing"].id
    session.add(edited_claim)
    session.commit()

    initial_claim_count = len(claims)

    # Rerun the pipeline
    job2 = Job(
        project_id=project.id,
        handover_id=handover.id,
        kind="handover_pipeline",
        status="queued",
    )
    session.add(job2)
    session.commit()
    run_handover_pipeline(job2.id, handover.id, project.id)

    # Verify:
    # 1. Total claims count did not explode/duplicate
    new_claims = session.exec(select(Claim).where(Claim.handover_id == handover.id)).all()
    assert len(new_claims) == initial_claim_count

    # 2. Human edited claim survived untouched
    survived = session.get(Claim, edited_claim.id)
    assert survived is not None
    assert survived.text == "CRITICAL HUMAN EDIT: Webhook signature verification verified by Aarav."
    assert survived.status == "edited"
    assert survived.origin == "human"


# ---------------------------------------------------------------------------
# 5. Job Status & SSE Stream Test
# ---------------------------------------------------------------------------


def test_job_status_and_sse_events_api(client: TestClient, session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    users = session.exec(select(User)).all()
    lead = next(u for u in users if u.role == "lead")

    job = Job(
        project_id=project.id,
        kind="handover_pipeline",
        status="done",
        stage="complete",
        progress=100,
        log=[
            {"stage": "extract", "progress": 50, "message": "Extracted 12 claims"},
            {"stage": "complete", "progress": 100, "message": "Done"},
        ],
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": lead.email, "password": "password123"},
    )
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Polling GET /jobs/{id}
    res = client.get(f"/api/v1/jobs/{job.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "done"
    assert data["progress"] == 100

    # SSE GET /jobs/{id}/events
    sse_res = client.get(f"/api/v1/jobs/{job.id}/events")
    assert sse_res.status_code == 200
    assert "text/event-stream" in sse_res.headers["content-type"]
    assert "Extracted 12 claims" in sse_res.text


# ---------------------------------------------------------------------------
# 6. Full Acceptance Flow Test
# ---------------------------------------------------------------------------


def test_full_acceptance_sequence(client: TestClient, session: Session) -> None:
    """Acceptance: single sequence (login -> load demo -> create handover -> run -> poll)

    yields an in_review handover with claims and plan.
    """
    # 1. Login
    # Seed users first
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    users = session.exec(select(User)).all()
    by_role = {u.role: u for u in users}

    lead = by_role["lead"]
    outgoing = by_role["outgoing"]
    successor = by_role["successor"]

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": lead.email, "password": "password123"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Handover
    create_res = client.post(
        f"/api/v1/projects/{project.id}/handovers",
        json={
            "outgoing_user_id": outgoing.id,
            "successor_user_id": successor.id,
            "lead_user_id": lead.id,
            "due_date": "2026-11-20T00:00:00Z",
            "notes": "Acceptance sequence test handover",
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    handover_id = create_res.json()["id"]

    # 3. Trigger Pipeline Run
    run_res = client.post(f"/api/v1/handovers/{handover_id}/run", headers=headers)
    assert run_res.status_code == 202
    job_id = run_res.json()["id"]

    # Execute pipeline synchronously to completion
    run_handover_pipeline(job_id, handover_id, project.id)

    # 4. Poll Job Status
    job_res = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert job_res.status_code == 200
    assert job_res.json()["status"] == "done"

    # 5. Verify Handover details
    ho_res = client.get(f"/api/v1/handovers/{handover_id}", headers=headers)
    assert ho_res.status_code == 200
    assert ho_res.json()["status"] == "in_review"

    # 6. Verify Claims
    claims_res = client.get(f"/api/v1/handovers/{handover_id}/claims", headers=headers)
    assert claims_res.status_code == 200
    claims = claims_res.json()
    assert len(claims) > 0
    # Verified claims are present
    assert any("PR #89" in c["text"] or "jwt" in c["text"].lower() for c in claims)

    # 7. Verify Onboarding Plan
    plan_res = client.get(f"/api/v1/handovers/{handover_id}/plan", headers=headers)
    assert plan_res.status_code == 200
    plan_items = plan_res.json()
    assert len(plan_items) > 0
    assert all(len(pi["claim_ids"]) > 0 for pi in plan_items)


def test_graph_and_timeline_endpoints(client: TestClient, session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    lead = session.exec(select(User).where(User.role == "lead")).first()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": lead.email, "password": "password123"},
    )
    assert login_res.status_code == 200
    headers = {"Authorization": f"Bearer {login_res.json()['token']}"}

    # Create handover
    ho_res = client.post(
        f"/api/v1/projects/{project.id}/handovers",
        json={
            "outgoing_user_id": lead.id,
            "successor_user_id": lead.id,
            "lead_user_id": lead.id,
            "notes": "Graph and timeline validation handover",
        },
        headers=headers,
    )
    assert ho_res.status_code == 201
    handover_id = ho_res.json()["id"]

    # 1. Test Graph Endpoint
    graph_res = client.get(f"/api/v1/handovers/{handover_id}/graph", headers=headers)
    assert graph_res.status_code == 200
    graph_data = graph_res.json()
    assert "nodes" in graph_data
    assert "edges" in graph_data
    assert len(graph_data["nodes"]) >= 4

    # Verify ledger-sync bus factor warning
    ledger_node = next((n for n in graph_data["nodes"] if n["id"] == "ledger-sync"), None)
    assert ledger_node is not None
    assert ledger_node["bus_factor_risk"] == "high"
    assert ledger_node["undocumented"] is True
    assert ledger_node["owner"] == "Aarav Kulkarni"

    # Verify DEPENDS_ON edges
    dep_edges = [e for e in graph_data["edges"] if e["type"] == "DEPENDS_ON"]
    assert len(dep_edges) >= 3

    # 2. Test Timeline Endpoint
    timeline_res = client.get(f"/api/v1/handovers/{handover_id}/timeline", headers=headers)
    assert timeline_res.status_code == 200
    timeline_data = timeline_res.json()
    assert len(timeline_data["events"]) >= 5
    assert len(timeline_data["links"]) >= 2

    # Verify Redis -> JWT supersession
    supersedes_links = [lnk for lnk in timeline_data["links"] if lnk["type"] == "SUPERSEDES"]
    assert len(supersedes_links) >= 2
    assert any(
        lnk["src_id"] == "event-redis-adr3" and lnk["dst_id"] == "event-jwt-pr89" for lnk in supersedes_links
    )
    assert any(
        lnk["src_id"] == "event-mongo-rfc7" and lnk["dst_id"] == "event-postgres-pr42"
        for lnk in supersedes_links
    )

    # Verify unresolved rate-limit conflict link
    conflict_links = [lnk for lnk in timeline_data["links"] if lnk["type"] == "CONFLICT"]
    assert len(conflict_links) >= 1
    assert any(
        lnk["src_id"] == "event-rate-100" and lnk["dst_id"] == "event-rate-500" for lnk in conflict_links
    )
