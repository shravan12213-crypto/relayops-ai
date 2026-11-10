"""Unit and integration tests for projects router and global handovers endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import Project, User
from app.routers.sources import execute_demo_load


def test_list_and_get_projects(client: TestClient, session: Session) -> None:
    execute_demo_load(session)
    lead = session.exec(select(User).where(User.email == "meera@payflow.dev")).one()

    # Login as lead
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": lead.email, "password": "password123"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # List projects
    res = client.get("/api/v1/projects", headers=headers)
    assert res.status_code == 200
    projects = res.json()
    assert len(projects) >= 1
    payflow = next(p for p in projects if p["slug"] == "payflow")
    assert payflow["name"] == "PayFlow"
    assert payflow["default_branch"] == "main"

    # Get single project
    detail_res = client.get(f"/api/v1/projects/{payflow['id']}", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == payflow["id"]


def test_create_project(client: TestClient, session: Session) -> None:
    execute_demo_load(session)
    lead = session.exec(select(User).where(User.email == "meera@payflow.dev")).one()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": lead.email, "password": "password123"},
    )
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "New Alpha Service",
        "description": "Next-gen service",
        "repo_url": "https://github.com/payflow/alpha",
    }
    create_res = client.post("/api/v1/projects", json=payload, headers=headers)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["slug"] == "new-alpha-service"
    assert created["name"] == "New Alpha Service"


def test_list_global_handovers(client: TestClient, session: Session) -> None:
    execute_demo_load(session)
    lead = session.exec(select(User).where(User.email == "meera@payflow.dev")).one()
    outgoing = session.exec(select(User).where(User.email == "aarav@payflow.dev")).one()
    successor = session.exec(select(User).where(User.email == "kabir@payflow.dev")).one()
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": lead.email, "password": "password123"},
    )
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Empty initially
    res_empty = client.get("/api/v1/handovers", headers=headers)
    assert res_empty.status_code == 200
    assert res_empty.json() == []

    # Create handover
    create_res = client.post(
        f"/api/v1/projects/{project.id}/handovers",
        json={
            "outgoing_user_id": outgoing.id,
            "successor_user_id": successor.id,
            "lead_user_id": lead.id,
            "notes": "Global handover list test",
        },
        headers=headers,
    )
    assert create_res.status_code == 201

    res = client.get("/api/v1/handovers", headers=headers)
    assert res.status_code == 200
    handovers = res.json()
    assert isinstance(handovers, list)
    assert len(handovers) == 1
    assert handovers[0]["notes"] == "Global handover list test"
