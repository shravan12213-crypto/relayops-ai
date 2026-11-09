"""Tests for successor portal: role views, delivery, plan, receipts, copilot,
export, and clearance firewall.

Enforces:
- Non-negotiable product rule #4: Access control applied BEFORE retrieval/LLM (SQL filter).
- Contractor firewall test: contractor NEVER receives clearance-2 text anywhere (view, chat context, export).
- Copilot grounding: answers PAY-142 with citations, refuses on undocumented topics.
- Dual sign-off delivery requirement: lead-only delivery of signed handover.
- Export formatting: contains cryptographic hashes, scorecard, and signatures.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import create_access_token
from app.handover import create_snapshot, execute_signoff
from app.models import (
    Claim,
    Handover,
    PlanItem,
    Project,
    User,
)
from app.routers.sources import execute_demo_load

CONFIDENTIAL_PLANTED_STRINGS = [
    "david.vance@acquirercorp.com",
    "+1-555-019-2834",
    "slack_th_leads_compensation",
    "Confidential lead item",
]


@pytest.fixture
def portal_setup(session: Session) -> dict[str, Any]:
    """Seed demo data, create a signed handover, and prepare role actors."""
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    users = session.exec(select(User)).all()
    by_role = {u.role: u for u in users}

    # Ensure contractor has clearance 1
    contractor = by_role["contractor"]
    contractor.clearance = 1
    session.add(contractor)

    # Lead has clearance 3
    lead = by_role["lead"]
    lead.clearance = 3
    session.add(lead)

    handover = Handover(
        project_id=project.id,
        outgoing_user_id=by_role["outgoing"].id,
        successor_user_id=by_role["successor"].id,
        lead_user_id=by_role["lead"].id,
        status="in_review",
        current_version=1,
    )
    session.add(handover)
    session.commit()
    session.refresh(handover)

    # Add claims: one internal (clearance 1), one confidential (clearance 2)
    c_public = Claim(
        project_id=project.id,
        handover_id=handover.id,
        section="webhook",
        kind="architecture_decision",
        text="Production webhook retry policy sets max_attempts to 5",
        status="accepted",
        confidence=1.0,
        sensitivity=1,
        origin="llm",
        evidence=[{"artifact_id": "PR-65", "source_uri": "https://github.com/payflow/payflow/pull/65"}],
    )
    c_confidential = Claim(
        project_id=project.id,
        handover_id=handover.id,
        section="acquirercorp_blocker",
        kind="blocker",
        text=(
            "PAY-142 escalation contact for AcquirerCorp is David Vance "
            "(david.vance@acquirercorp.com, +1-555-019-2834)"
        ),
        status="accepted",
        confidence=0.9,
        sensitivity=2,  # CONFIDENTIAL!
        origin="llm",
        evidence=[{"artifact_id": "msg_leads_vendor_01", "source_uri": "slack://leads-private"}],
    )
    session.add(c_public)
    session.add(c_confidential)

    # Add plan item
    p1 = PlanItem(
        handover_id=handover.id,
        day_bucket="d1_7",
        title="Verify webhook retry worker locally",
        description="Run local docker dispatcher tests",
        status="todo",
        claim_ids=[c_public.id],
    )
    session.add(p1)
    session.commit()

    # Freeze Snapshot v1
    v1 = create_snapshot(session, handover.id, actor_id=lead.id, reason="Portal test baseline snapshot")

    # Both parties sign v1 to transition handover to 'signed'
    execute_signoff(session, handover.id, by_role["outgoing"], version=1, comment="Aarav signoff")
    execute_signoff(session, handover.id, lead, version=1, comment="Meera signoff")

    session.refresh(handover)
    assert handover.status == "signed"

    return {
        "project": project,
        "handover": handover,
        "users": by_role,
        "c_public": c_public,
        "c_confidential": c_confidential,
        "v1": v1,
    }


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Clearance Firewall Tests (Contractor Security Boundary)
# ---------------------------------------------------------------------------


def test_contractor_firewall_view(client: TestClient, portal_setup: dict[str, Any]) -> None:
    """Contractor never receives sensitivity-2 text in handover view."""
    handover = portal_setup["handover"]
    contractor = portal_setup["users"]["contractor"]

    res = client.get(
        f"/api/v1/handovers/{handover.id}/view",
        headers=auth_headers(contractor),
    )
    assert res.status_code == 200
    res_text = res.text

    # Assert ZERO planted confidential strings appear anywhere in the HTTP response body
    for planted in CONFIDENTIAL_PLANTED_STRINGS:
        assert (
            planted not in res_text
        ), f"Firewall breach! Planted string '{planted}' leaked to contractor view."

    data = res.json()
    assert data["viewing_role"] == "contractor"
    assert data["effective_clearance"] <= 1

    # Verify that the sensitivity 2 claim was masked
    masked_claims = [c for c in data["claims"] if c.get("is_masked") is True]
    assert len(masked_claims) >= 1
    assert "Restricted: requires clearance 2" in masked_claims[0]["text"]


def test_contractor_firewall_chat(client: TestClient, portal_setup: dict[str, Any]) -> None:
    """Contractor Copilot retrieval never accesses sensitivity-2 artifacts or claims."""
    handover = portal_setup["handover"]
    contractor = portal_setup["users"]["contractor"]

    # Contractor queries Copilot about the confidential escalation contact
    chat_res = client.post(
        f"/api/v1/handovers/{handover.id}/chat",
        json={"message": "Who is the AcquirerCorp escalation contact for PAY-142?"},
        headers=auth_headers(contractor),
    )
    assert chat_res.status_code == 200
    res_text = chat_res.text

    # Assert ZERO planted confidential strings leak in the chat response
    for planted in CONFIDENTIAL_PLANTED_STRINGS:
        assert (
            planted not in res_text
        ), f"Firewall breach! Planted string '{planted}' leaked in contractor Copilot chat."


def test_contractor_firewall_export(client: TestClient, portal_setup: dict[str, Any]) -> None:
    """Contractor exports (JSON, Markdown, HTML) never contain sensitivity-2 text."""
    handover = portal_setup["handover"]
    contractor = portal_setup["users"]["contractor"]
    headers = auth_headers(contractor)

    # 1. JSON Export
    res_json = client.get(f"/api/v1/handovers/{handover.id}/export?format=json", headers=headers)
    assert res_json.status_code == 200
    for planted in CONFIDENTIAL_PLANTED_STRINGS:
        assert planted not in res_json.text, f"Firewall breach in JSON export for '{planted}'"

    # 2. Markdown Export
    res_md = client.get(f"/api/v1/handovers/{handover.id}/export?format=md", headers=headers)
    assert res_md.status_code == 200
    for planted in CONFIDENTIAL_PLANTED_STRINGS:
        assert planted not in res_md.text, f"Firewall breach in Markdown export for '{planted}'"

    # 3. HTML Export
    res_html = client.get(f"/api/v1/handovers/{handover.id}/export?format=html", headers=headers)
    assert res_html.status_code == 200
    for planted in CONFIDENTIAL_PLANTED_STRINGS:
        assert planted not in res_html.text, f"Firewall breach in HTML export for '{planted}'"


# ---------------------------------------------------------------------------
# 2. Role-Scoped Perspectives & RBAC Preview Tests
# ---------------------------------------------------------------------------


def test_role_scoped_views(client: TestClient, portal_setup: dict[str, Any]) -> None:
    handover = portal_setup["handover"]
    lead = portal_setup["users"]["lead"]
    successor = portal_setup["users"]["successor"]
    headers_lead = auth_headers(lead)

    # 1. Lead previews Junior view via ?as=junior -> Includes 'why it matters' glossary
    junior_res = client.get(f"/api/v1/handovers/{handover.id}/view?as=junior", headers=headers_lead)
    assert junior_res.status_code == 200
    junior_data = junior_res.json()
    assert junior_data["viewing_role"] == "junior"
    assert junior_data["glossary"] is not None
    assert any("why_it_matters" in item for item in junior_data["glossary"])

    # 2. Lead previews Auditor view via ?as=auditor -> Text withheld, scorecard and audit verification present
    auditor_res = client.get(f"/api/v1/handovers/{handover.id}/view?as=auditor", headers=headers_lead)
    assert auditor_res.status_code == 200
    auditor_data = auditor_res.json()
    assert auditor_data["viewing_role"] == "auditor"
    assert all("[Audit Mode: Text withheld]" in c["text"] for c in auditor_data["claims"])
    assert auditor_data["audit_verification"] is not None
    assert auditor_data["audit_verification"]["chain_valid"] is True

    # 3. RBAC Preview: Successor attempts to preview as lead -> 403 Forbidden
    bad_preview = client.get(
        f"/api/v1/handovers/{handover.id}/view?as=lead",
        headers=auth_headers(successor),
    )
    assert bad_preview.status_code == 403


# ---------------------------------------------------------------------------
# 3. Delivery Transition Tests
# ---------------------------------------------------------------------------


def test_handover_delivery_lifecycle(
    client: TestClient, session: Session, portal_setup: dict[str, Any]
) -> None:
    handover = portal_setup["handover"]
    lead = portal_setup["users"]["lead"]
    outgoing = portal_setup["users"]["outgoing"]

    # 1. Non-lead attempts delivery -> 403 Forbidden
    res_out = client.post(
        f"/api/v1/handovers/{handover.id}/deliver",
        headers=auth_headers(outgoing),
    )
    assert res_out.status_code == 403

    # 2. Lead delivers signed handover -> 200 OK, status moves to 'delivered'
    res_deliver = client.post(
        f"/api/v1/handovers/{handover.id}/deliver",
        headers=auth_headers(lead),
    )
    assert res_deliver.status_code == 200
    data = res_deliver.json()
    assert data["status"] == "delivered"
    assert "delivered_at" in data

    session.refresh(handover)
    assert handover.status == "delivered"


# ---------------------------------------------------------------------------
# 4. Copilot Grounding & Deterministic Refusal Tests
# ---------------------------------------------------------------------------


def test_copilot_grounded_answer_and_refusal(client: TestClient, portal_setup: dict[str, Any]) -> None:
    handover = portal_setup["handover"]
    lead = portal_setup["users"]["lead"]
    headers = auth_headers(lead)

    # 1. Undocumented topic -> Deterministic Refusal
    undoc_res = client.post(
        f"/api/v1/handovers/{handover.id}/chat",
        json={"message": "What is our quantum computing rollout plan for 2027?"},
        headers=headers,
    )
    assert undoc_res.status_code == 200
    undoc_data = undoc_res.json()
    assert undoc_data["refused"] is True
    assert undoc_data["can_answer"] is False
    assert "I can't verify this from the handover evidence" in undoc_data["answer"]
    assert "outgoing contributor" in undoc_data["answer"].lower()

    # 2. Grounded question on PAY-142 blocker -> Answer with valid citations
    doc_res = client.post(
        f"/api/v1/handovers/{handover.id}/chat",
        json={"message": "What is the status of open blocker PAY-142 for vendor sandbox access?"},
        headers=headers,
    )
    assert doc_res.status_code == 200
    doc_data = doc_res.json()
    assert doc_data["refused"] is False
    assert doc_data["can_answer"] is True
    assert len(doc_data["citations"]) > 0
    assert any("142" in c["id"] or "PAY-142" in c.get("snippet", "") for c in doc_data["citations"])


# ---------------------------------------------------------------------------
# 5. 30-Day Plan & Comprehension Receipts Tests
# ---------------------------------------------------------------------------


def test_plan_and_receipts_workflow(
    client: TestClient, session: Session, portal_setup: dict[str, Any]
) -> None:
    handover = portal_setup["handover"]
    successor = portal_setup["users"]["successor"]
    headers = auth_headers(successor)

    # 1. Retrieve Plan with linked claims
    plan_res = client.get(f"/api/v1/handovers/{handover.id}/plan", headers=headers)
    assert plan_res.status_code == 200
    plan_items = plan_res.json()
    assert len(plan_items) >= 1
    item = plan_items[0]
    assert "linked_claims" in item
    assert len(item["linked_claims"]) >= 1

    # 2. Update Plan Item status from 'todo' to 'doing'
    patch_res = client.patch(
        f"/api/v1/handovers/{handover.id}/plan/{item['id']}",
        json={"status": "doing", "assignee": successor.id},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "doing"
    assert patch_res.json()["assignee"] == successor.id

    # 3. Add Custom Plan Item
    create_res = client.post(
        f"/api/v1/handovers/{handover.id}/plan",
        json={
            "day_bucket": "d8_14",
            "title": "Set up staging payment simulation suite",
            "description": "Verify webhook idempotency under load",
            "priority": "high",
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    assert create_res.json()["title"] == "Set up staging payment simulation suite"

    # 4. Acknowledge Section Receipt
    receipt_res = client.post(
        f"/api/v1/handovers/{handover.id}/receipts",
        json={"section": "webhook", "comprehension_note": "Reviewed PR #65 exponential retry logic"},
        headers=headers,
    )
    assert receipt_res.status_code == 201
    assert receipt_res.json()["section"] == "webhook"

    # 5. Check Receipts Progress Percentage
    progress_res = client.get(f"/api/v1/handovers/{handover.id}/receipts", headers=headers)
    assert progress_res.status_code == 200
    prog_data = progress_res.json()
    assert "progress_pct" in prog_data
    assert prog_data["progress_pct"] > 0
    assert "webhook" in prog_data["acknowledged_sections"]


# ---------------------------------------------------------------------------
# 6. Export Content & Hashes Verification Test
# ---------------------------------------------------------------------------


def test_export_contains_hashes_and_signatures(client: TestClient, portal_setup: dict[str, Any]) -> None:
    handover = portal_setup["handover"]
    lead = portal_setup["users"]["lead"]
    v1 = portal_setup["v1"]
    headers = auth_headers(lead)

    # 1. JSON Export verification
    res_json = client.get(f"/api/v1/handovers/{handover.id}/export?format=json", headers=headers)
    assert res_json.status_code == 200
    j_data = res_json.json()
    assert j_data["hash"] == v1.hash
    assert "scorecard" in j_data
    assert len(j_data["signatures"]) >= 2

    # 2. Markdown Export verification
    res_md = client.get(f"/api/v1/handovers/{handover.id}/export?format=md", headers=headers)
    assert res_md.status_code == 200
    md_text = res_md.text
    assert v1.hash in md_text
    assert "Verification Scorecard" in md_text
    assert "Dual Sign-off Signatures" in md_text
    assert "[^" in md_text  # Footnote citations present

    # 3. HTML Export verification
    res_html = client.get(f"/api/v1/handovers/{handover.id}/export?format=html", headers=headers)
    assert res_html.status_code == 200
    html_text = res_html.text
    assert v1.hash in html_text
    assert "@media print" in html_text  # Print-to-PDF styles present
    assert "Verification Scorecard" in html_text
    assert "fn-" in html_text  # Footnotes present


def test_copilot_history_feedback_and_questions(
    client: TestClient, portal_setup: dict[str, Any]
) -> None:
    handover = portal_setup["handover"]
    successor = portal_setup["users"]["successor"]
    headers = auth_headers(successor)

    # 1. Ask a question to generate a chat message
    chat_res = client.post(
        f"/api/v1/handovers/{handover.id}/chat",
        json={"message": "What is the status of open blocker PAY-142 for vendor sandbox access?"},
        headers=headers,
    )
    assert chat_res.status_code == 200
    msg_id = chat_res.json()["message_id"]

    # 2. Get message history
    history_res = client.get(
        f"/api/v1/handovers/{handover.id}/chat/messages",
        headers=headers,
    )
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) >= 2  # user + assistant

    # 3. Submit thumbs up feedback
    fb_res = client.post(
        f"/api/v1/handovers/{handover.id}/chat/messages/{msg_id}/feedback",
        json={"feedback": "up"},
        headers=headers,
    )
    assert fb_res.status_code == 200
    assert fb_res.json()["feedback"] == "up"

    # 4. Create an open question for outgoing owner ("Ask Aarav")
    q_res = client.post(
        f"/api/v1/handovers/{handover.id}/questions",
        json={
            "title": "Webhook Retry Backoff in Staging",
            "question": "Does the staging mock acquirer simulate 429 Too Many Requests?",
        },
        headers=headers,
    )
    assert q_res.status_code == 201
    q_data = q_res.json()
    assert q_data["type"] == "open_question"
    assert "Webhook Retry" in q_data["title"]


def test_p18_acceptance_kabir_dev_and_drag_drop(
    client: TestClient, portal_setup: dict[str, Any]
) -> None:
    """Explicitly verify P18 Acceptance Criteria:
    - Kabir (successor) shows only clearance-allowed content
    - Dev (contractor) cannot see any confidential text anywhere including copilot answers
    - Refusal path works on undocumented questions
    - Drag-and-drop bucket updates persist across reload
    """
    handover = portal_setup["handover"]
    users = portal_setup["users"]
    kabir = users["successor"]  # Kabir Sharma
    dev = users["contractor"]  # Dev Mukherjee

    # 1. Kabir (successor, clearance 1) views handover -> Clearance-2 is masked
    res_kabir = client.get(
        f"/api/v1/handovers/{handover.id}/view",
        headers=auth_headers(kabir),
    )
    assert res_kabir.status_code == 200
    kabir_view = res_kabir.json()
    assert kabir_view["effective_clearance"] == 1
    # Check that confidential claim is masked
    masked_claims = [c for c in kabir_view["claims"] if c.get("is_masked") is True]
    assert len(masked_claims) >= 1
    assert "david.vance@acquirercorp.com" not in res_kabir.text

    # 2. Dev (contractor, clearance 1) cannot see ANY confidential text anywhere
    res_dev_view = client.get(
        f"/api/v1/handovers/{handover.id}/view",
        headers=auth_headers(dev),
    )
    assert res_dev_view.status_code == 200
    for secret in CONFIDENTIAL_PLANTED_STRINGS:
        assert secret not in res_dev_view.text

    # Dev queries Copilot on confidential contact -> Firewall blocks leakage
    chat_dev = client.post(
        f"/api/v1/handovers/{handover.id}/chat",
        json={"message": "Who is David Vance and what is his email and phone?"},
        headers=auth_headers(dev),
    )
    assert chat_dev.status_code == 200
    for secret in CONFIDENTIAL_PLANTED_STRINGS:
        assert secret not in chat_dev.text

    # 3. Refusal path on undocumented topic
    refusal_res = client.post(
        f"/api/v1/handovers/{handover.id}/chat",
        json={"message": "What is our quantum computing rollout plan for 2027?"},
        headers=auth_headers(kabir),
    )
    assert refusal_res.status_code == 200
    refusal_data = refusal_res.json()
    assert refusal_data["refused"] is True
    assert refusal_data["can_answer"] is False
    assert "I can't verify this from the handover evidence" in refusal_data["answer"]

    # 4. Drag-and-drop persistence across reload
    plan_list = client.get(
        f"/api/v1/handovers/{handover.id}/plan",
        headers=auth_headers(kabir),
    ).json()
    assert len(plan_list) >= 1
    target_item = plan_list[0]
    orig_bucket = target_item["day_bucket"]
    new_bucket = "d15_30" if orig_bucket != "d15_30" else "d8_14"

    # Drag to new bucket
    patch_res = client.patch(
        f"/api/v1/handovers/{handover.id}/plan/{target_item['id']}",
        json={"day_bucket": new_bucket},
        headers=auth_headers(kabir),
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["day_bucket"] == new_bucket

    # Reload and verify persistence
    reloaded_plan = client.get(
        f"/api/v1/handovers/{handover.id}/plan",
        headers=auth_headers(kabir),
    ).json()
    reloaded_item = next(i for i in reloaded_plan if i["id"] == target_item["id"])
    assert reloaded_item["day_bucket"] == new_bucket
