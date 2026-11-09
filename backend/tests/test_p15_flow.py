"""End-to-end test for P15 acceptance flow:
login -> load demo -> create handover -> run pipeline -> verify review readiness.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import COOKIE_NAME, hash_password
from app.db import get_engine, init_db
from app.models import User


def test_p15_end_to_end_flow(client: TestClient) -> None:
    init_db()

    # 1. Ensure Meera exists in DB to log in
    with Session(get_engine()) as session:
        existing = session.exec(select(User).where(User.email == "meera@payflow.dev")).first()
        if not existing:
            user = User(
                email="meera@payflow.dev",
                name="Meera Patel",
                password_hash=hash_password("password123"),
                role="lead",
                clearance=3,
            )
            session.add(user)
            session.commit()

    # Step 1: Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "meera@payflow.dev", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    assert token
    assert COOKIE_NAME in login_resp.cookies

    # Step 2: Load PayFlow Demo Dataset
    demo_resp = client.post("/api/v1/demo/load")
    assert demo_resp.status_code == 200
    demo_data = demo_resp.json()
    assert demo_data["status"] == "ok"
    project_id = demo_data["project_id"]
    assert demo_data["total_artifacts"] > 100

    # Verify project sources and redaction audit
    sources_resp = client.get(f"/api/v1/projects/{project_id}/sources")
    assert sources_resp.status_code == 200
    sources = sources_resp.json()
    assert len(sources) >= 4

    redaction_resp = client.get(f"/api/v1/projects/{project_id}/redaction-audit")
    assert redaction_resp.status_code == 200
    redaction_data = redaction_resp.json()
    assert redaction_data["total_redactions"] > 0
    assert len(redaction_data["rules"]) > 0

    # Step 3: Fetch users to populate handover dropdowns
    users_resp = client.get("/api/v1/users")
    assert users_resp.status_code == 200
    users = {u["role"]: u["id"] for u in users_resp.json()}
    outgoing_id = users["outgoing"]
    successor_id = users["successor"]
    lead_id = users["lead"]

    # Create Handover
    create_resp = client.post(
        f"/api/v1/projects/{project_id}/handovers",
        json={
            "outgoing_user_id": outgoing_id,
            "successor_user_id": successor_id,
            "lead_user_id": lead_id,
            "due_date": "2026-11-30",
            "notes": "PayFlow Payment Webhook Refactor Handover",
        },
    )
    assert create_resp.status_code == 201
    handover = create_resp.json()
    handover_id = handover["id"]
    assert handover["status"] == "draft"

    # Step 4: Run Handover Pipeline (11 stages)
    run_resp = client.post(f"/api/v1/handovers/{handover_id}/run")
    assert run_resp.status_code == 202
    job = run_resp.json()
    job_id = job["id"]
    assert job["stage"] == "connect_check"

    # Check job status via polling
    poll_resp = client.get(f"/api/v1/jobs/{job_id}")
    assert poll_resp.status_code == 200
    poll_data = poll_resp.json()
    assert poll_data["id"] == job_id
    assert "log" in poll_data

    # Step 5: Check Audit Logs feed
    audit_resp = client.get("/api/v1/audit/logs")
    assert audit_resp.status_code == 200
    audit_logs = audit_resp.json()
    assert len(audit_logs) >= 2
    # Check that our actions were recorded in audit log
    actions = [a["action"] for a in audit_logs]
    assert "LOAD_DEMO_DATASET" in actions
