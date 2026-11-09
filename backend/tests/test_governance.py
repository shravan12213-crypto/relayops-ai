"""Tests for Governance, Audit Chain Verification, Policy Matrix,
Project Members Management, and System Administration.

Enforces:
- Lead and Auditor role boundaries on compliance/audit endpoints.
- 403 Forbidden for non-privileged users.
- Tamper detection on the SHA-256 audit log hash chain.
- Project member management with clearance caps.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import create_access_token
from app.cli import main as cli_main
from app.models import Project, User
from app.routers.sources import execute_demo_load


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def gov_setup(session: Session) -> dict[str, Any]:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    users = session.exec(select(User)).all()
    by_role = {u.role: u for u in users}

    lead = by_role["lead"]
    auditor = by_role["auditor"]
    successor = by_role["successor"]
    contractor = by_role["contractor"]

    return {
        "project": project,
        "lead": lead,
        "auditor": auditor,
        "successor": successor,
        "contractor": contractor,
        "all_users": by_role,
    }


def test_audit_logs_rbac_and_filtering(client: TestClient, gov_setup: dict[str, Any]) -> None:
    lead = gov_setup["lead"]
    auditor = gov_setup["auditor"]
    successor = gov_setup["successor"]
    contractor = gov_setup["contractor"]

    # 1. Non-privileged users (successor, contractor) get 403 Forbidden
    res_succ = client.get("/api/v1/audit/logs", headers=auth_headers(successor))
    assert res_succ.status_code == 403
    assert res_succ.json()["error"]["code"] == "FORBIDDEN"

    res_cont = client.get("/api/v1/audit/logs", headers=auth_headers(contractor))
    assert res_cont.status_code == 403

    # 2. Auditor and Lead have access
    res_audit = client.get("/api/v1/audit/logs", headers=auth_headers(auditor))
    assert res_audit.status_code == 200
    logs = res_audit.json()
    assert isinstance(logs, list)
    assert len(logs) > 0
    assert "X-Total-Count" in res_audit.headers

    # 3. Paginated format test
    res_paged = client.get("/api/v1/audit/logs?paged=true&page=1&page_size=5", headers=auth_headers(lead))
    assert res_paged.status_code == 200
    paged_data = res_paged.json()
    assert "items" in paged_data
    assert "total" in paged_data
    assert paged_data["page"] == 1
    assert len(paged_data["items"]) <= 5


def test_verify_chain_and_cli_tamper(client: TestClient, gov_setup: dict[str, Any]) -> None:
    lead = gov_setup["lead"]
    auditor = gov_setup["auditor"]
    successor = gov_setup["successor"]

    # 1. Non-privileged user blocked from chain verification
    res_bad = client.post("/api/v1/audit/verify-chain", headers=auth_headers(successor))
    assert res_bad.status_code == 403

    # 2. Before tamper: chain is valid
    res_valid = client.post("/api/v1/audit/verify-chain", headers=auth_headers(auditor))
    assert res_valid.status_code == 200
    data_valid = res_valid.json()
    assert data_valid["valid"] is True
    assert data_valid["tampered_seq"] is None

    # CLI verify-chain passes
    rc_cli = cli_main(["verify-chain"])
    assert rc_cli == 0

    # 3. Tamper via CLI
    rc_tamper = cli_main(["tamper"])
    assert rc_tamper == 0

    # 4. After tamper: verify-chain API reports tampered sequence
    res_tampered = client.post("/api/v1/audit/verify-chain", headers=auth_headers(lead))
    assert res_tampered.status_code == 200
    data_tampered = res_tampered.json()
    assert data_tampered["valid"] is False
    assert data_tampered["tampered_seq"] is not None
    assert "mismatch" in data_tampered["error"].lower() or "tampered" in data_tampered["error"].lower()

    # CLI verify-chain returns failure code 1
    rc_fail = cli_main(["verify-chain"])
    assert rc_fail == 1


def test_policy_matrix_endpoint(client: TestClient, gov_setup: dict[str, Any]) -> None:
    lead = gov_setup["lead"]
    res = client.get("/api/v1/policy", headers=auth_headers(lead))
    assert res.status_code == 200
    data = res.json()

    assert "roles" in data
    assert "clearance_levels" in data
    assert "rules" in data

    roles = data["roles"]
    assert "lead" in roles
    assert "auditor" in roles
    assert "contractor" in roles

    # Verify contractor rule
    contractor_rules = [r for r in data["rules"] if r["role"] == "contractor"]
    assert all(r["claims_max_sensitivity"] <= 1 for r in contractor_rules)

    # Verify auditor rule
    auditor_rules = [r for r in data["rules"] if r["role"] == "auditor"]
    assert all(r["artifact_bodies_visible"] is False for r in auditor_rules)


def test_sensitivity_distribution(client: TestClient, gov_setup: dict[str, Any]) -> None:
    lead = gov_setup["lead"]
    project = gov_setup["project"]

    res = client.get(
        f"/api/v1/projects/{project.id}/sensitivity-distribution",
        headers=auth_headers(lead),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == project.id
    assert data["total_artifacts"] > 0
    assert len(data["buckets"]) == 4  # Levels 0, 1, 2, 3
    assert any(b["artifacts_count"] > 0 for b in data["buckets"])


def test_project_members_management(client: TestClient, gov_setup: dict[str, Any]) -> None:
    lead = gov_setup["lead"]
    successor = gov_setup["successor"]
    contractor = gov_setup["contractor"]
    project = gov_setup["project"]

    # 1. Non-lead user cannot manage members
    res_bad = client.post(
        f"/api/v1/projects/{project.id}/members",
        json={"user_id": contractor.id, "project_role": "external_developer"},
        headers=auth_headers(successor),
    )
    assert res_bad.status_code == 403

    # 2. List members
    list_res = client.get(
        f"/api/v1/projects/{project.id}/members",
        headers=auth_headers(lead),
    )
    assert list_res.status_code == 200
    members = list_res.json()
    assert len(members) >= 1

    # 3. Update existing member clearance
    existing_user_id = members[0]["user_id"]
    patch_res = client.patch(
        f"/api/v1/projects/{project.id}/members/{existing_user_id}",
        json={"project_role": "senior_maintainer", "clearance": 2},
        headers=auth_headers(lead),
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["project_role"] == "senior_maintainer"

    # 4. Removing a member
    del_res = client.delete(
        f"/api/v1/projects/{project.id}/members/{existing_user_id}",
        headers=auth_headers(lead),
    )
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "ok"


def test_system_status_and_reset(client: TestClient, gov_setup: dict[str, Any]) -> None:
    lead = gov_setup["lead"]
    successor = gov_setup["successor"]

    # 1. System status endpoint
    status_res = client.get("/api/v1/system/status", headers=auth_headers(successor))
    assert status_res.status_code == 200
    s_data = status_res.json()
    assert "llm_mode" in s_data
    assert "provider" in s_data
    assert "total_projects" in s_data

    # 2. Reset demo dataset as non-lead -> 403
    reset_bad = client.post("/api/v1/system/reset-demo", headers=auth_headers(successor))
    assert reset_bad.status_code == 403

    # 3. Reset demo dataset as lead -> 200
    reset_ok = client.post("/api/v1/system/reset-demo", headers=auth_headers(lead))
    assert reset_ok.status_code == 200
    assert reset_ok.json()["status"] == "ok"
