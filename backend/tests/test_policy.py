"""Table-driven unit tests for ABAC policy rules."""

from __future__ import annotations

import pytest

from app.policy import (
    allowed_actions,
    can_view_artifact,
    can_view_claim,
    effective_clearance,
    mask_claim,
)


class DummyUser:
    def __init__(self, id: str, role: str, clearance: int, project_ids: set[str] | None = None) -> None:
        self.id = id
        self.role = role
        self.clearance = clearance
        self.project_ids = project_ids or {"p1"}


class DummyArtifact:
    def __init__(self, id: str, project_id: str, sensitivity: int) -> None:
        self.id = id
        self.project_id = project_id
        self.sensitivity = sensitivity


class DummyClaim:
    def __init__(self, id: str, sensitivity: int, text: str = "Secret architecture note") -> None:
        self.id = id
        self.sensitivity = sensitivity
        self.text = text
        self.evidence = [{"artifact_id": "art_1", "snippet": "Evidence text"}]


@pytest.mark.parametrize(
    ("role", "clearance", "expected_effective"),
    [
        ("lead", 3, 3),
        ("lead", 2, 2),
        ("outgoing", 2, 2),
        ("successor", 1, 1),
        ("contractor", 3, 1),  # Capped at 1
        ("contractor", 2, 1),  # Capped at 1
        ("contractor", 1, 1),
        ("auditor", 3, 1),  # Capped at 1
        ("auditor", 2, 1),  # Capped at 1
    ],
)
def test_effective_clearance_caps(role: str, clearance: int, expected_effective: int) -> None:
    user = DummyUser("u1", role, clearance)
    assert effective_clearance(user) == expected_effective


@pytest.mark.parametrize(
    ("role", "clearance", "sensitivity", "is_member", "can_view"),
    [
        # Public (0)
        ("successor", 1, 0, True, True),
        ("contractor", 1, 0, True, True),
        # Internal (1)
        ("successor", 1, 1, True, True),
        ("contractor", 1, 1, True, True),
        ("contractor", 0, 1, True, False),
        # Confidential (2) - contractor is capped at 1, so cannot view
        ("contractor", 3, 2, True, False),
        ("lead", 2, 2, True, True),
        ("successor", 1, 2, True, False),
        # Restricted (3)
        ("lead", 3, 3, True, True),
        ("outgoing", 2, 3, True, False),
        # Auditor: never allowed raw artifact bodies
        ("auditor", 3, 0, True, False),
        ("auditor", 3, 1, True, False),
        # Non-member
        ("lead", 3, 1, False, False),
    ],
)
def test_can_view_artifact(
    role: str,
    clearance: int,
    sensitivity: int,
    is_member: bool,
    can_view: bool,
) -> None:
    user = DummyUser("u1", role, clearance, project_ids={"p1"} if is_member else {"p2"})
    art = DummyArtifact("art1", "p1", sensitivity)
    assert can_view_artifact(user, art) == can_view


@pytest.mark.parametrize(
    ("role", "clearance", "sensitivity", "expected_view"),
    [
        ("lead", 2, 2, True),
        ("lead", 1, 2, False),
        ("successor", 1, 1, True),
        ("successor", 1, 2, False),
        ("contractor", 3, 2, False),  # Capped at 1
        ("contractor", 1, 1, True),
        ("auditor", 2, 1, True),  # Auditor can view claim metadata up to cap 1
        ("auditor", 2, 2, False),
    ],
)
def test_can_view_claim(role: str, clearance: int, sensitivity: int, expected_view: bool) -> None:
    user = DummyUser("u1", role, clearance)
    claim = DummyClaim("c1", sensitivity)
    assert can_view_claim(user, claim) == expected_view


def test_mask_claim_redaction() -> None:
    claim = DummyClaim("c1", sensitivity=2, text="Top secret internal roadmap")

    # High clearance user sees plain claim
    lead = DummyUser("lead_1", "lead", 2)
    unmasked = mask_claim(claim, lead)
    assert unmasked["is_masked"] is False
    assert unmasked["text"] == "Top secret internal roadmap"
    assert len(unmasked["evidence"]) == 1

    # Low clearance user gets masked claim
    successor = DummyUser("succ_1", "successor", 1)
    masked = mask_claim(claim, successor)
    assert masked["is_masked"] is True
    assert masked["text"] == "Restricted: requires clearance 2"
    assert masked["evidence"] == []


def test_allowed_actions_matrix() -> None:
    lead = DummyUser("u1", "lead", 3)
    outgoing = DummyUser("u2", "outgoing", 2)
    successor = DummyUser("u3", "successor", 1)
    auditor = DummyUser("u4", "auditor", 1)
    contractor = DummyUser("u5", "contractor", 1)

    lead_actions = allowed_actions(lead)
    outgoing_actions = allowed_actions(outgoing)
    successor_actions = allowed_actions(successor)
    auditor_actions = allowed_actions(auditor)
    contractor_actions = allowed_actions(contractor)

    # Signoff allowed only for outgoing + lead
    assert "signoff" in lead_actions
    assert "signoff" in outgoing_actions
    assert "signoff" not in successor_actions
    assert "signoff" not in auditor_actions
    assert "signoff" not in contractor_actions

    # Edit claims allowed only for lead + outgoing
    assert "edit_claims" in lead_actions
    assert "edit_claims" in outgoing_actions
    assert "edit_claims" not in successor_actions

    # Deliver only by lead
    assert "deliver" in lead_actions
    assert "deliver" not in outgoing_actions

    # View audit log allowed for lead + auditor
    assert "view_audit_log" in lead_actions
    assert "view_audit_log" in auditor_actions
    assert "view_audit_log" not in successor_actions
    assert "view_audit_log" not in contractor_actions

    # Acknowledge receipt only by successor
    assert "acknowledge_receipt" in successor_actions
    assert "acknowledge_receipt" not in lead_actions

