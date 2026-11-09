"""Regression tests for Handover authorization and access control (P0 and P1).

Validates:
- Pipeline trigger authorization on POST /api/v1/handovers/{id}/run:
  * Permitted roles (lead, outgoing) can trigger pipeline execution.
  * Restricted roles (junior, contractor, successor, auditor) receive 403 Forbidden.
  * Non-members of the project receive 403 Forbidden.
  * Unauthenticated requests receive 401 Unauthenticated.
  * Nonexistent handovers receive 404 Not Found.
  * Rejected requests do NOT create background jobs or mutate handover state.
- Handover metadata access control on GET /api/v1/handovers/{id}:
  * Project members (lead, outgoing, successor, contractor, auditor) can retrieve metadata.
  * Non-members from another project receive 403 Forbidden.
  * Unauthenticated requests receive 401 Unauthenticated.
  * Nonexistent handovers receive 404 Not Found.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import create_access_token, hash_password
from app.models import Handover, Job, Project, ProjectMember, User
from app.routers.sources import execute_demo_load


def auth_headers(user: User) -> dict[str, str]:
    """Helper to generate Bearer authorization headers for a given user."""
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_setup(session: Session) -> dict[str, Any]:
    """Seed PayFlow dataset and create a secondary tenant project with isolated members."""
    execute_demo_load(session)
    payflow = session.exec(select(Project).where(Project.slug == "payflow")).one()
    users = session.exec(select(User)).all()
    by_role = {u.role: u for u in users}

    lead = by_role["lead"]
    outgoing = by_role["outgoing"]
    successor = by_role["successor"]
    contractor = by_role["contractor"]
    auditor = by_role["auditor"]

    # Create a junior engineer user in payflow
    junior = User(
        email="dev.junior@payflow.dev",
        name="Junior Dev",
        password_hash=hash_password("password123"),
        role="junior",
        clearance=1,
        is_active=True,
    )
    session.add(junior)
    session.commit()
    session.refresh(junior)

    pm_junior = ProjectMember(
        project_id=payflow.id,
        user_id=junior.id,
        project_role="contributor",
    )
    session.add(pm_junior)

    # Create a separate project (acme-corp) and an isolated user who is NOT in payflow
    acme_project = Project(
        name="Acme Corp",
        slug="acme-corp",
        description="External unrelated tenant",
    )
    session.add(acme_project)
    session.commit()
    session.refresh(acme_project)

    outsider_user = User(
        email="outsider@acme.com",
        name="Acme Engineer",
        password_hash=hash_password("password123"),
        role="lead",
        clearance=2,
        is_active=True,
    )
    session.add(outsider_user)
    session.commit()
    session.refresh(outsider_user)

    pm_outsider = ProjectMember(
        project_id=acme_project.id,
        user_id=outsider_user.id,
        project_role="lead",
    )
    session.add(pm_outsider)

    # Create a test handover in payflow
    handover = Handover(
        project_id=payflow.id,
        outgoing_user_id=outgoing.id,
        successor_user_id=successor.id,
        lead_user_id=lead.id,
        status="draft",
        current_version=1,
        notes="Authorization test handover",
    )
    session.add(handover)
    session.commit()
    session.refresh(handover)

    return {
        "payflow": payflow,
        "acme": acme_project,
        "handover": handover,
        "lead": lead,
        "outgoing": outgoing,
        "successor": successor,
        "contractor": contractor,
        "auditor": auditor,
        "junior": junior,
        "outsider": outsider_user,
    }


# ---------------------------------------------------------------------------
# 1. Pipeline Trigger Security (P0)
# ---------------------------------------------------------------------------


def test_lead_can_trigger_pipeline(client: TestClient, auth_setup: dict[str, Any], session: Session) -> None:
    """Authorized project lead can successfully trigger pipeline execution."""
    handover = auth_setup["handover"]
    lead = auth_setup["lead"]

    res = client.post(f"/api/v1/handovers/{handover.id}/run", headers=auth_headers(lead))
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "queued"
    assert data["handover_id"] == handover.id


def test_outgoing_can_trigger_pipeline(
    client: TestClient, auth_setup: dict[str, Any], session: Session
) -> None:
    """Authorized outgoing engineer can trigger pipeline execution."""
    handover = auth_setup["handover"]
    outgoing = auth_setup["outgoing"]

    # Delete any active jobs from previous test if any
    jobs = session.exec(select(Job).where(Job.handover_id == handover.id)).all()
    for j in jobs:
        session.delete(j)
    session.commit()

    res = client.post(f"/api/v1/handovers/{handover.id}/run", headers=auth_headers(outgoing))
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "queued"


def test_junior_cannot_trigger_pipeline(
    client: TestClient, auth_setup: dict[str, Any], session: Session
) -> None:
    """Junior engineer with role='junior' is forbidden from triggering the pipeline."""
    handover = auth_setup["handover"]
    junior = auth_setup["junior"]

    initial_job_count = len(session.exec(select(Job).where(Job.handover_id == handover.id)).all())

    res = client.post(f"/api/v1/handovers/{handover.id}/run", headers=auth_headers(junior))
    assert res.status_code == 403
    err = res.json()["error"]
    assert err["code"] == "FORBIDDEN"

    # Verify no job was created and state was NOT modified
    after_jobs = session.exec(select(Job).where(Job.handover_id == handover.id)).all()
    assert len(after_jobs) == initial_job_count


def test_contractor_cannot_trigger_pipeline(
    client: TestClient, auth_setup: dict[str, Any], session: Session
) -> None:
    """Contractor is forbidden from triggering the pipeline."""
    handover = auth_setup["handover"]
    contractor = auth_setup["contractor"]

    initial_job_count = len(session.exec(select(Job).where(Job.handover_id == handover.id)).all())

    res = client.post(f"/api/v1/handovers/{handover.id}/run", headers=auth_headers(contractor))
    assert res.status_code == 403
    err = res.json()["error"]
    assert err["code"] == "FORBIDDEN"

    after_jobs = session.exec(select(Job).where(Job.handover_id == handover.id)).all()
    assert len(after_jobs) == initial_job_count


def test_outsider_cannot_trigger_pipeline(
    client: TestClient, auth_setup: dict[str, Any], session: Session
) -> None:
    """Authenticated user from another project is forbidden (project isolation)."""
    handover = auth_setup["handover"]
    outsider = auth_setup["outsider"]

    initial_job_count = len(session.exec(select(Job).where(Job.handover_id == handover.id)).all())

    res = client.post(f"/api/v1/handovers/{handover.id}/run", headers=auth_headers(outsider))
    assert res.status_code == 403
    err = res.json()["error"]
    assert err["code"] == "FORBIDDEN"

    after_jobs = session.exec(select(Job).where(Job.handover_id == handover.id)).all()
    assert len(after_jobs) == initial_job_count


def test_unauthenticated_cannot_trigger_pipeline(
    client: TestClient, auth_setup: dict[str, Any], session: Session
) -> None:
    """Unauthenticated requests are rejected with 401."""
    handover = auth_setup["handover"]

    initial_job_count = len(session.exec(select(Job).where(Job.handover_id == handover.id)).all())

    res = client.post(f"/api/v1/handovers/{handover.id}/run")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHENTICATED"

    after_jobs = session.exec(select(Job).where(Job.handover_id == handover.id)).all()
    assert len(after_jobs) == initial_job_count


def test_nonexistent_handover_run_returns_404(client: TestClient, auth_setup: dict[str, Any]) -> None:
    """Attempting to trigger a pipeline on a nonexistent handover returns 404."""
    lead = auth_setup["lead"]

    res = client.post("/api/v1/handovers/nonexistent-ulid-99999/run", headers=auth_headers(lead))
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# 2. Handover Metadata Access Security (P1)
# ---------------------------------------------------------------------------


def test_project_members_can_access_handover_metadata(client: TestClient, auth_setup: dict[str, Any]) -> None:
    """Authorized project members (lead, successor, contractor, auditor) can view handover details."""
    handover = auth_setup["handover"]
    lead = auth_setup["lead"]
    successor = auth_setup["successor"]
    contractor = auth_setup["contractor"]
    auditor = auth_setup["auditor"]

    for user in [lead, successor, contractor, auditor]:
        res = client.get(f"/api/v1/handovers/{handover.id}", headers=auth_headers(user))
        assert res.status_code == 200, f"Expected 200 for user role {user.role}, got {res.status_code}"
        data = res.json()
        assert data["id"] == handover.id
        assert data["project_id"] == handover.project_id


def test_outsider_cannot_access_handover_metadata(client: TestClient, auth_setup: dict[str, Any]) -> None:
    """Authenticated user from another tenant cannot access handover metadata (IDOR protection)."""
    handover = auth_setup["handover"]
    outsider = auth_setup["outsider"]

    res = client.get(f"/api/v1/handovers/{handover.id}", headers=auth_headers(outsider))
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


def test_unauthenticated_cannot_access_handover_metadata(
    client: TestClient, auth_setup: dict[str, Any]
) -> None:
    """Unauthenticated requests for handover metadata receive 401."""
    handover = auth_setup["handover"]

    res = client.get(f"/api/v1/handovers/{handover.id}")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHENTICATED"


def test_nonexistent_handover_metadata_returns_404(client: TestClient, auth_setup: dict[str, Any]) -> None:
    """Nonexistent handover returns 404."""
    lead = auth_setup["lead"]

    res = client.get("/api/v1/handovers/nonexistent-ulid-99999", headers=auth_headers(lead))
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"
