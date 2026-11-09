"""Attribute-Based Access Control (ABAC) policy rules.

Pure functions without database access for transparent, table-driven unit testing.
Enforces clearance levels (0-3), role caps, and pre-retrieval authorization.
"""

from __future__ import annotations

from typing import Any

# Sensitivity levels:
# 0: Public
# 1: Internal (company-wide)
# 2: Confidential (leads, HR, vendor pricing, credentials)
# 3: Restricted (executive/legal only)

# Roles:
# - lead: Full administrative control, can sign off, deliver, and view audit logs.
# - outgoing: The departing engineer; can edit claims, resolve ambiguities, and sign off.
# - successor: The onboarding engineer; can view permitted handover content and acknowledge receipts.
# - contractor: External contributor; clearance capped at 1.
# - auditor: Compliance reviewer; clearance capped at 1, metadata/scorecards only (no raw bodies).


def _get_clearance(user: Any) -> int:
    if isinstance(user, dict):
        return int(user.get("clearance", 0))
    return int(getattr(user, "clearance", 0))


def _get_role(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("role", "")).lower()
    return str(getattr(user, "role", "")).lower()


def _get_sensitivity(resource: Any) -> int:
    if isinstance(resource, dict):
        return int(resource.get("sensitivity", 0))
    return int(getattr(resource, "sensitivity", 0))


def can_view_artifact(
    user: Any,
    artifact: Any,
    project_member_ids: set[str] | list[str] | None = None,
) -> bool:
    """Check if user can view an artifact: clearance >= sensitivity AND user is project member."""
    # Auditors are restricted to metadata/scorecards, not raw artifact bodies
    if _get_role(user) == "auditor":
        return False

    clearance = effective_clearance(user)
    sensitivity = _get_sensitivity(artifact)
    if clearance < sensitivity:
        return False

    # Check project membership
    if project_member_ids is not None:
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        return user_id in project_member_ids

    # If user object carries project_ids or is_member flag
    if hasattr(user, "project_ids") and getattr(artifact, "project_id", None):
        return artifact.project_id in user.project_ids

    if hasattr(user, "is_member"):
        return bool(user.is_member)

    return True


def can_view_claim(user: Any, claim: Any) -> bool:
    """Check if user can view a claim: clearance >= claim.sensitivity."""
    clearance = effective_clearance(user)
    sensitivity = _get_sensitivity(claim)
    return clearance >= sensitivity


def effective_clearance(user: Any, handover: Any = None) -> int:
    """Compute effective clearance. Contractor and auditor are capped at 1."""
    role = _get_role(user)
    base_clearance = _get_clearance(user)

    if role in ("contractor", "auditor"):
        return min(base_clearance, 1)

    return base_clearance


def mask_claim(claim: Any, user: Any) -> dict[str, Any]:
    """Return claim dictionary; if user lacks clearance, text is masked and evidence stripped."""
    if hasattr(claim, "model_dump"):
        data = claim.model_dump()
    elif hasattr(claim, "dict"):
        data = claim.dict()
    elif isinstance(claim, dict):
        data = dict(claim)
    else:
        data = {
            "id": getattr(claim, "id", ""),
            "handover_id": getattr(claim, "handover_id", ""),
            "section": getattr(claim, "section", ""),
            "kind": getattr(claim, "kind", ""),
            "text": getattr(claim, "text", ""),
            "status": getattr(claim, "status", "draft"),
            "confidence": getattr(claim, "confidence", 1.0),
            "sensitivity": getattr(claim, "sensitivity", 1),
            "evidence": getattr(claim, "evidence", []),
            "origin": getattr(claim, "origin", "llm"),
            "order_index": getattr(claim, "order_index", 0),
        }

    sensitivity = data.get("sensitivity", 1)
    if can_view_claim(user, claim):
        data["is_masked"] = False
        return data

    data["text"] = f"Restricted: requires clearance {sensitivity}"
    data["evidence"] = []
    data["is_masked"] = True
    return data


def allowed_actions(user: Any, handover: Any = None) -> set[str]:
    """Return set of action strings allowed for the user's role on a handover."""
    role = _get_role(user)
    actions: set[str] = set()

    # Universal read access (within clearance limits)
    actions.add("view_handover")

    if role in ("lead", "outgoing"):
        actions.add("edit_claims")
        actions.add("create_claim")
        actions.add("resolve_ambiguity")
        actions.add("create_snapshot")
        actions.add("signoff")
        actions.add("run_pipeline")
        actions.add("chat")

    if role == "lead":
        actions.add("waive_ambiguity")
        actions.add("deliver")
        actions.add("view_audit_log")
        actions.add("manage_members")

    if role == "auditor":
        actions.add("view_audit_log")
        actions.add("verify_chain")

    if role == "successor":
        actions.add("acknowledge_receipt")
        actions.add("update_plan_status")
        actions.add("chat")

    if role == "contractor":
        actions.add("chat")

    return actions

