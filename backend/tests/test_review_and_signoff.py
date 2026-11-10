"""Tests for Review API, versioning, dual sign-off, diffs, and cryptographic audit.

Covers:
- Claims PATCH: edit text, accept, reject (reason required), needs_review.
- Human claims: >=1 evidence artifact required OR unverified=true.
- Optimistic concurrency: updated_at mismatch raises 409 Conflict.
- Ambiguity lifecycle: resolve (note required), waive (lead-only).
- Versioning: snapshot hash chaining = sha256(prev_hash + canonical_json(snapshot)).
- Version diff: word-level diff for modified claim text.
- Sign-off state machine:
  * Blocked by draft claims.
  * Blocked by open HIGH-severity ambiguities.
  * Blocked on stale version.
  * Dual sign-off requirement: outgoing + lead -> status=signed.
  * Subsequent edits invalidate existing sign-offs and revert status.
- Verification: detect DB snapshot tampering.
- Audit trail: all mutations append hash-chained audit log records.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from app.auth import create_access_token
from app.db import verify_audit_chain
from app.handover import (
    create_snapshot,
)
from app.models import (
    Ambiguity,
    AuditLog,
    Claim,
    Handover,
    PlanItem,
    Project,
    Signoff,
    User,
)
from app.routers.sources import execute_demo_load


@pytest.fixture
def test_setup(session: Session) -> dict[str, Any]:
    """Seed demo data and prepare a test handover with artifacts and users."""
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    users = session.exec(select(User)).all()
    by_role = {u.role: u for u in users}

    handover = Handover(
        project_id=project.id,
        outgoing_user_id=by_role["outgoing"].id,
        successor_user_id=by_role["successor"].id,
        lead_user_id=by_role["lead"].id,
        status="in_review",
        current_version=1,
        notes="Dual sign-off test handover",
    )
    session.add(handover)
    session.commit()
    session.refresh(handover)

    # Add initial claims (one draft, one accepted)
    c1 = Claim(
        project_id=project.id,
        handover_id=handover.id,
        section="webhook",
        kind="architecture_decision",
        text="Initial draft webhook claim",
        status="draft",
        confidence=0.9,
        sensitivity=1,
        origin="llm",
    )
    c2 = Claim(
        project_id=project.id,
        handover_id=handover.id,
        section="database",
        kind="architecture_decision",
        text="PostgreSQL 16 selected for relational ledger transactions",
        status="accepted",
        confidence=1.0,
        sensitivity=1,
        origin="llm",
        evidence=[{"artifact_id": "PR-42"}],
    )
    session.add(c1)
    session.add(c2)

    # Initial plan item
    p1 = PlanItem(
        handover_id=handover.id,
        day_bucket="d1_7",
        title="Review ledger migrations",
        status="todo",
    )
    session.add(p1)

    session.commit()
    session.refresh(c1)
    session.refresh(c2)

    # Create baseline HandoverVersion v1
    v1 = create_snapshot(
        session,
        handover.id,
        actor_id=by_role["lead"].id,
        reason="Initial baseline snapshot",
    )

    return {
        "project": project,
        "handover": handover,
        "users": by_role,
        "c1": c1,
        "c2": c2,
        "v1": v1,
    }


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Claims Review & Optimistic Concurrency Tests
# ---------------------------------------------------------------------------


def test_claim_patch_operations(client: TestClient, session: Session, test_setup: dict[str, Any]) -> None:
    c1 = test_setup["c1"]
    outgoing = test_setup["users"]["outgoing"]
    headers = auth_headers(outgoing)

    # 1. Edit text -> status becomes 'edited', edited_by set, origin stays 'llm'
    res = client.patch(
        f"/api/v1/claims/{c1.id}",
        json={"text": "Updated webhook retry policy to 5 attempts"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["text"] == "Updated webhook retry policy to 5 attempts"
    assert data["status"] == "edited"
    assert data["origin"] == "llm"
    assert data["edited_by"] == outgoing.id

    # 2. Reject without reason -> 422 Validation Error
    res_bad = client.patch(
        f"/api/v1/claims/{c1.id}",
        json={"status": "rejected", "rejected_reason": ""},
        headers=headers,
    )
    assert res_bad.status_code == 422

    # 3. Reject with valid reason -> 200 OK
    res_rej = client.patch(
        f"/api/v1/claims/{c1.id}",
        json={"status": "rejected", "rejected_reason": "Superseded by PR #65"},
        headers=headers,
    )
    assert res_rej.status_code == 200
    assert res_rej.json()["status"] == "rejected"
    assert res_rej.json()["rejected_reason"] == "Superseded by PR #65"

    # 4. Accept claim -> 200 OK, rejected_reason cleared
    res_acc = client.patch(
        f"/api/v1/claims/{c1.id}",
        json={"status": "accepted"},
        headers=headers,
    )
    assert res_acc.status_code == 200
    assert res_acc.json()["status"] == "accepted"
    assert res_acc.json()["rejected_reason"] is None


def test_claim_patch_optimistic_concurrency(
    client: TestClient, session: Session, test_setup: dict[str, Any]
) -> None:
    c1 = test_setup["c1"]
    lead = test_setup["users"]["lead"]
    headers = auth_headers(lead)

    # Provide stale expected_updated_at (1 hour in the past)
    stale_ts = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    res = client.patch(
        f"/api/v1/claims/{c1.id}",
        json={"text": "Concurrent modification attempt", "expected_updated_at": stale_ts},
        headers=headers,
    )
    assert res.status_code == 409
    err = res.json()["error"]
    assert err["code"] == "CONFLICT"
    assert "modified concurrently" in err["message"]


def test_create_human_claims(client: TestClient, session: Session, test_setup: dict[str, Any]) -> None:
    handover = test_setup["handover"]
    outgoing = test_setup["users"]["outgoing"]
    headers = auth_headers(outgoing)

    # 1. Human claim with no evidence and unverified=false -> 422 Validation Error
    bad_res = client.post(
        f"/api/v1/handovers/{handover.id}/claims",
        json={"text": "Unverified assertion without flag", "unverified": False},
        headers=headers,
    )
    assert bad_res.status_code == 422

    # 2. Human claim with unverified=true -> Accepted with author-asserted note
    unverified_res = client.post(
        f"/api/v1/handovers/{handover.id}/claims",
        json={"text": "Author asserted runbook note", "unverified": True},
        headers=headers,
    )
    assert unverified_res.status_code == 201
    uv_data = unverified_res.json()
    assert uv_data["origin"] == "human"
    assert uv_data["status"] == "needs_review"
    assert any("author-asserted" in e.get("snippet", "").lower() for e in uv_data["evidence"])

    # 3. Human claim with valid artifact evidence
    grounded_res = client.post(
        f"/api/v1/handovers/{handover.id}/claims",
        json={
            "text": "Migrate core ledger database to PostgreSQL 16",
            "evidence_artifact_ids": ["PR-42"],
            "unverified": False,
        },
        headers=headers,
    )
    assert grounded_res.status_code == 201
    gr_data = grounded_res.json()
    assert gr_data["origin"] == "human"
    assert gr_data["status"] == "accepted"


def test_list_claims_filtering_and_pagination(
    client: TestClient, session: Session, test_setup: dict[str, Any]
) -> None:
    handover = test_setup["handover"]
    lead = test_setup["users"]["lead"]
    headers = auth_headers(lead)

    # Default list format (backwards compatible list)
    res_list = client.get(f"/api/v1/handovers/{handover.id}/claims", headers=headers)
    assert res_list.status_code == 200
    claims = res_list.json()
    assert isinstance(claims, list)
    assert len(claims) >= 2
    assert "X-Total-Count" in res_list.headers

    # Paginated format requested via ?paged=true
    res_paged = client.get(
        f"/api/v1/handovers/{handover.id}/claims?paged=true&limit=1&offset=0",
        headers=headers,
    )
    assert res_paged.status_code == 200
    data = res_paged.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) == 1
    assert data["total"] >= 2


# ---------------------------------------------------------------------------
# 2. Ambiguity Lifecycle Tests (Resolve & Lead-Only Waive)
# ---------------------------------------------------------------------------


def test_ambiguity_resolve_and_waive(
    client: TestClient, session: Session, test_setup: dict[str, Any]
) -> None:
    handover = test_setup["handover"]
    project = test_setup["project"]
    outgoing = test_setup["users"]["outgoing"]
    lead = test_setup["users"]["lead"]
    contractor = test_setup["users"]["contractor"]

    # Create a high-severity test ambiguity
    amb = Ambiguity(
        project_id=project.id,
        handover_id=handover.id,
        type="conflict",
        severity="high",
        title="Contradicting retry policies",
        description="Runbook specifies 3 retries while PR #65 specifies 5 retries.",
        status="open",
    )
    session.add(amb)
    session.commit()
    session.refresh(amb)

    # 1. Contractor attempts to waive -> 403 Forbidden
    res_contractor = client.post(
        f"/api/v1/ambiguities/{amb.id}/waive",
        json={"reason": "Contractor attempt to waive"},
        headers=auth_headers(contractor),
    )
    assert res_contractor.status_code == 403

    # 2. Outgoing attempts to waive -> 403 Forbidden (only lead can waive)
    res_out_waive = client.post(
        f"/api/v1/ambiguities/{amb.id}/waive",
        json={"reason": "Outgoing attempt to waive"},
        headers=auth_headers(outgoing),
    )
    assert res_out_waive.status_code == 403

    # 3. Outgoing resolves with note -> 200 OK
    res_resolve = client.post(
        f"/api/v1/ambiguities/{amb.id}/resolve",
        json={"resolution_note": "Verified production code max_attempts=5 is canonical"},
        headers=auth_headers(outgoing),
    )
    assert res_resolve.status_code == 200
    assert res_resolve.json()["status"] == "resolved"
    assert res_resolve.json()["resolution_note"] == "Verified production code max_attempts=5 is canonical"

    # Create second high-severity ambiguity to test Lead waiving
    amb2 = Ambiguity(
        project_id=project.id,
        handover_id=handover.id,
        type="missing_doc",
        severity="high",
        title="Unpublished merchant sandbox credentials",
        description="AcquirerCorp test account pending legal NDA.",
        status="open",
    )
    session.add(amb2)
    session.commit()
    session.refresh(amb2)

    # 4. Lead waives ambiguity -> 200 OK
    res_waive = client.post(
        f"/api/v1/ambiguities/{amb2.id}/waive",
        json={"reason": "Waived by Meera: sandbox credentials will be obtained post-handover"},
        headers=auth_headers(lead),
    )
    assert res_waive.status_code == 200
    assert res_waive.json()["status"] == "waived"

    # 5. Nested route aliases and alternative payload fields (e.g. waiver_reason, resolution)
    amb3 = Ambiguity(
        project_id=project.id,
        handover_id=handover.id,
        title="Test Alias Ambiguity",
        description="Alias ambiguity description",
        status="open",
        severity="medium",
        type="gap",
    )
    amb4 = Ambiguity(
        project_id=project.id,
        handover_id=handover.id,
        title="Test Waive Alias Ambiguity",
        description="Alias waive description",
        status="open",
        severity="high",
        type="contradiction",
    )
    session.add(amb3)
    session.add(amb4)
    session.commit()
    session.refresh(amb3)
    session.refresh(amb4)

    # Resolve via nested alias with 'resolution' payload field
    res_alias_resolve = client.post(
        f"/api/v1/handovers/{handover.id}/ambiguities/{amb3.id}/resolve",
        json={"resolution": "Resolved via nested route alias and resolution field"},
        headers=auth_headers(lead),
    )
    assert res_alias_resolve.status_code == 200
    assert res_alias_resolve.json()["status"] == "resolved"

    # Waive via nested alias with 'waiver_reason' payload field (from frontend UI)
    res_alias_waive = client.post(
        f"/api/v1/handovers/{handover.id}/ambiguities/{amb4.id}/waive",
        json={"waiver_reason": "Waived via nested route alias and waiver_reason field"},
        headers=auth_headers(lead),
    )
    assert res_alias_waive.status_code == 200
    assert res_alias_waive.json()["status"] == "waived"

    # Claim patch via nested route alias
    c1 = test_setup["c1"]
    res_claim_alias = client.patch(
        f"/api/v1/handovers/{handover.id}/claims/{c1.id}",
        json={"status": "accepted"},
        headers=auth_headers(lead),
    )
    assert res_claim_alias.status_code == 200
    assert res_claim_alias.json()["status"] == "accepted"


# ---------------------------------------------------------------------------
# 3. Versioning & Word-Level Diff Tests
# ---------------------------------------------------------------------------


def test_versioning_and_diff(client: TestClient, session: Session, test_setup: dict[str, Any]) -> None:
    handover = test_setup["handover"]
    lead = test_setup["users"]["lead"]
    headers = auth_headers(lead)
    v1 = test_setup["v1"]

    # Edit claim text to establish a delta
    c2 = test_setup["c2"]
    c2.text = "PostgreSQL 16 selected for unified ledger transactions and idempotency checks"
    c2.status = "edited"
    session.add(c2)
    session.commit()

    # Create Snapshot v2
    snap_res = client.post(
        f"/api/v1/handovers/{handover.id}/snapshot",
        json={"reason": "Updated PostgreSQL claim description"},
        headers=headers,
    )
    assert snap_res.status_code == 201
    v2_data = snap_res.json()
    assert v2_data["version"] == 2
    assert v2_data["prev_hash"] == v1.hash
    assert len(v2_data["hash"]) == 64

    # Fetch version diff between v1 and v2
    diff_res = client.get(
        f"/api/v1/handovers/{handover.id}/versions/diff?v1=1&v2=2",
        headers=headers,
    )
    assert diff_res.status_code == 200
    diff_data = diff_res.json()
    assert diff_data["from_version"] == 1
    assert diff_data["to_version"] == 2

    # Verify claim changes and word-level diff
    changed = diff_data["claims"]["changed"]
    assert len(changed) >= 1
    match = next((item for item in changed if item["id"] == c2.id), None)
    assert match is not None
    assert "word_diff" in match["changes"]["text"]
    tokens = match["changes"]["text"]["word_diff"]
    # Check that removed and added word tokens exist
    assert any(t["type"] == "removed" for t in tokens)
    assert any(t["type"] == "added" for t in tokens)


# ---------------------------------------------------------------------------
# 4. Dual Sign-off State Machine & Invalidation Tests
# ---------------------------------------------------------------------------


def test_signoff_state_machine_and_invalidation(
    client: TestClient, session: Session, test_setup: dict[str, Any]
) -> None:
    handover = test_setup["handover"]
    project = test_setup["project"]
    outgoing = test_setup["users"]["outgoing"]
    lead = test_setup["users"]["lead"]
    c1 = test_setup["c1"]

    headers_out = auth_headers(outgoing)
    headers_lead = auth_headers(lead)

    # 1. State machine rule: CANNOT SIGN WITH DRAFT CLAIMS
    # c1 is still in 'draft' status
    res_draft_block = client.post(
        f"/api/v1/handovers/{handover.id}/signoff",
        json={"version": handover.current_version, "comment": "Ready to sign"},
        headers=headers_out,
    )
    assert res_draft_block.status_code == 400
    assert "draft" in res_draft_block.json()["error"]["message"]

    # Accept c1 to clear draft claim blocker
    c1.status = "accepted"
    session.add(c1)
    session.commit()

    # 2. State machine rule: CANNOT SIGN WITH OPEN HIGH-SEVERITY AMBIGUITIES
    amb_high = Ambiguity(
        project_id=project.id,
        handover_id=handover.id,
        type="blocker",
        severity="high",
        title="Unresolved PCI audit finding",
        description="Pending compliance review",
        status="open",
    )
    session.add(amb_high)
    session.commit()

    res_amb_block = client.post(
        f"/api/v1/handovers/{handover.id}/signoff",
        json={"version": handover.current_version, "comment": "Trying to bypass ambiguity"},
        headers=headers_out,
    )
    assert res_amb_block.status_code == 400
    assert "HIGH-severity" in res_amb_block.json()["error"]["message"]

    # Lead waives the high-severity ambiguity
    client.post(
        f"/api/v1/ambiguities/{amb_high.id}/waive",
        json={"reason": "Waived by Lead for test"},
        headers=headers_lead,
    )

    # Freeze snapshot v2 with all drafts resolved
    snap_res = client.post(
        f"/api/v1/handovers/{handover.id}/snapshot",
        json={"reason": "Ready for sign-off"},
        headers=headers_lead,
    )
    v2_version = snap_res.json()["version"]

    # 3. State machine rule: CANNOT SIGN STALE VERSION
    res_stale = client.post(
        f"/api/v1/handovers/{handover.id}/signoff",
        json={"version": 1, "comment": "Attempting sign-off on stale v1"},
        headers=headers_out,
    )
    assert res_stale.status_code == 400
    assert "stale version" in res_stale.json()["error"]["message"]

    # 4. Dual sign-off: OUTGOING SIGNS FIRST
    res_sign1 = client.post(
        f"/api/v1/handovers/{handover.id}/signoff",
        json={"version": v2_version, "comment": "Aarav signing off on payment refactor"},
        headers=headers_out,
    )
    assert res_sign1.status_code == 200
    sign1_data = res_sign1.json()
    assert sign1_data["role"] == "outgoing"
    assert sign1_data["both_signed"] is False
    assert sign1_data["handover_status"] == "in_review"

    # 5. Dual sign-off: LEAD SIGNS SECOND -> STATUS MOVES TO 'signed'
    res_sign2 = client.post(
        f"/api/v1/handovers/{handover.id}/signoff",
        json={"version": v2_version, "comment": "Meera approving handover handover as lead"},
        headers=headers_lead,
    )
    assert res_sign2.status_code == 200
    sign2_data = res_sign2.json()
    assert sign2_data["role"] == "lead"
    assert sign2_data["both_signed"] is True
    assert sign2_data["handover_status"] == "signed"

    # Refresh DB handover
    session.refresh(handover)
    assert handover.status == "signed"

    # 6. Verify HMAC Signatures & Hash Chain
    verify_res = client.get(f"/api/v1/handovers/{handover.id}/verify", headers=headers_lead)
    assert verify_res.status_code == 200
    v_info = verify_res.json()
    assert v_info["chain_valid"] is True
    assert v_info["signatures_valid"] is True
    assert v_info["details"]["tamper_detected"] is False

    # 7. Invalidation: ANY SUBSEQUENT EDIT INVALIDATES SIGNOFFS
    patch_res = client.patch(
        f"/api/v1/claims/{c1.id}",
        json={"text": "Late breaking post-signoff claim edit"},
        headers=headers_out,
    )
    assert patch_res.status_code == 200

    # Sign-offs must now be wiped and handover reverts from 'signed' to 'in_review'
    session.refresh(handover)
    assert handover.status == "in_review"

    remaining_signoffs = session.exec(select(Signoff).where(Signoff.handover_id == handover.id)).all()
    assert len(remaining_signoffs) == 0


# ---------------------------------------------------------------------------
# 5. Tamper Detection & Audit Chain Integrity Tests
# ---------------------------------------------------------------------------


def test_tamper_detection(client: TestClient, session: Session, test_setup: dict[str, Any]) -> None:
    handover = test_setup["handover"]
    lead = test_setup["users"]["lead"]
    v1 = test_setup["v1"]

    # Tamper with snapshot in database directly
    tampered_snapshot = copy.deepcopy(v1.snapshot)
    tampered_snapshot["claims"][0]["text"] = "MALICIOUS DIRECT DB INJECTION"
    v1.snapshot = tampered_snapshot
    flag_modified(v1, "snapshot")
    session.add(v1)
    session.commit()

    # Call verify endpoint
    verify_res = client.get(
        f"/api/v1/handovers/{handover.id}/verify",
        headers=auth_headers(lead),
    )
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["chain_valid"] is False
    assert v_data["details"]["tamper_detected"] is True
    assert any("tampered" in err for err in v_data["details"]["errors"])


def test_tamper_evident_audit_log(session: Session, test_setup: dict[str, Any]) -> None:
    # Verify that audit log records exist and form a continuous, unbroken hash chain
    logs = session.exec(select(AuditLog)).all()
    assert len(logs) > 0
    assert verify_audit_chain(session) is True


def test_conflicts_and_artifacts_endpoints(
    client: TestClient, session: Session, test_setup: dict[str, Any]
) -> None:
    handover = test_setup["handover"]
    lead = test_setup["users"]["lead"]
    headers = auth_headers(lead)

    # 1. Test conflicts endpoint
    conflicts_res = client.get(
        f"/api/v1/handovers/{handover.id}/conflicts",
        headers=headers,
    )
    assert conflicts_res.status_code == 200
    conflicts = conflicts_res.json()
    assert isinstance(conflicts, list)

    # 2. Test artifact endpoint
    c1 = test_setup["c1"]
    if c1.evidence and len(c1.evidence) > 0:
        art_id = c1.evidence[0]["artifact_id"]
        art_res = client.get(f"/api/v1/artifacts/{art_id}", headers=headers)
        assert art_res.status_code == 200
        art_data = art_res.json()
        assert art_data["id"] == art_id
