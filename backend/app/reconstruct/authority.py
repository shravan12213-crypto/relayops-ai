"""Source authority weighting and claim resolution engine.

Implements source authority weights and bi-temporal resolution rules:
- Newer + higher/equal authority supersedes older.
- Newer but lower authority does NOT supersede (flags a conflict).
- Contemporaneous disagreement at equal authority => UNRESOLVED.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

# Source authority hierarchy from RelayOps build plan
AUTHORITY_WEIGHTS: dict[str, float] = {
    "commit": 1.0,
    "pull_request": 1.0,
    "merged_pr": 1.0,
    "code_file": 1.0,
    "issue": 0.8,
    "issue_ticket": 0.8,
    "adr_doc": 0.6,
    "meeting_note": 0.6,
    "doc": 0.6,
    "runbook": 0.6,
    "branch": 0.5,
    "unmerged_pr": 0.5,
    "chat_thread": 0.4,
    "chat": 0.4,
}


def authority_for(artifact: Any) -> float:
    """Return authority score for an artifact, node, or kind string."""
    if hasattr(artifact, "authority") and artifact.authority is not None:
        return float(artifact.authority)

    kind = ""
    if hasattr(artifact, "kind"):
        kind = str(artifact.kind)
    elif hasattr(artifact, "type"):
        kind = str(artifact.type)
    elif isinstance(artifact, dict):
        kind = str(artifact.get("kind") or artifact.get("type") or "")
    elif isinstance(artifact, str):
        kind = artifact

    # Check unmerged flag in metadata
    if hasattr(artifact, "meta") and isinstance(artifact.meta, dict) and artifact.meta.get("merged") is False:
        return AUTHORITY_WEIGHTS["unmerged_pr"]

    return AUTHORITY_WEIGHTS.get(kind.lower(), 0.5)


class ResolutionStatus(StrEnum):
    SUPERSEDES = "SUPERSEDES"
    CONFLICT = "CONFLICT"
    UNRESOLVED = "UNRESOLVED"
    AGREES = "AGREES"


@dataclass
class ResolutionResult:
    status: ResolutionStatus
    winner: Any | None = None
    loser: Any | None = None
    reason: str = ""


def _extract_time(item: Any) -> datetime:
    for attr in ("valid_time", "valid_from", "occurred_at", "created_at"):
        if hasattr(item, attr) and getattr(item, attr) is not None:
            val = getattr(item, attr)
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
        if isinstance(item, dict) and item.get(attr):
            val = item[attr]
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
    return datetime.min


def resolve(claim_a: Any, claim_b: Any) -> ResolutionResult:
    """Resolve two contradictory or overlapping claims using temporal authority rules.

    Rules:
    1. Newer + higher/equal authority => SUPERSEDES (newer supersedes older).
    2. Newer + lower authority => CONFLICT (newer cannot override higher authority code/doc).
    3. Same-time (within 24h) + equal authority => UNRESOLVED.
    4. Same-time + unequal authority => CONFLICT (higher authority wins, flagged for review).
    """
    t_a = _extract_time(claim_a)
    t_b = _extract_time(claim_b)
    auth_a = authority_for(claim_a)
    auth_b = authority_for(claim_b)

    # Calculate temporal difference in seconds
    delta_seconds = (t_b - t_a).total_seconds()
    is_contemporaneous = abs(delta_seconds) < 86400  # Within 24 hours

    if is_contemporaneous:
        # Same-time resolution
        if abs(auth_a - auth_b) < 0.05:
            return ResolutionResult(
                status=ResolutionStatus.UNRESOLVED,
                winner=None,
                loser=None,
                reason=(
                    f"Contemporaneous disagreement at equal authority ({auth_a:.1f}). "
                    "Cannot automatically resolve; human review required."
                ),
            )
        if auth_a > auth_b:
            return ResolutionResult(
                status=ResolutionStatus.CONFLICT,
                winner=claim_a,
                loser=claim_b,
                reason=f"Resolved by source authority: {auth_a:.1f} vs {auth_b:.1f}",
            )
        return ResolutionResult(
            status=ResolutionStatus.CONFLICT,
            winner=claim_b,
            loser=claim_a,
            reason=f"Resolved by source authority: {auth_b:.1f} vs {auth_a:.1f}",
        )

    # One is older, one is newer
    if delta_seconds > 0:
        older, newer = claim_a, claim_b
        auth_older, auth_newer = auth_a, auth_b
    else:
        older, newer = claim_b, claim_a
        auth_older, auth_newer = auth_b, auth_a

    # Newer + higher/equal authority => SUPERSEDES
    if auth_newer >= auth_older:
        return ResolutionResult(
            status=ResolutionStatus.SUPERSEDES,
            winner=newer,
            loser=older,
            reason=(
                f"Newer item ({auth_newer:.1f}) supersedes older item ({auth_older:.1f}) "
                f"by temporal precedence and equal/higher source authority."
            ),
        )

    # Newer + lower authority => CONFLICT (does NOT supersede)
    return ResolutionResult(
        status=ResolutionStatus.CONFLICT,
        winner=older,
        loser=newer,
        reason=(
            f"Newer item has lower authority ({auth_newer:.1f}) than older item ({auth_older:.1f}); "
            "lower authority cannot supersede higher authority without verification."
        ),
    )
