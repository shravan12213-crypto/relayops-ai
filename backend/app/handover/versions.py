"""Handover versioning: snapshot freezing, hash chaining, and version diffing.

Freezes claims, ambiguities, plan items, and scorecard into an immutable
HandoverVersion record with cryptographic hash chaining:
    hash = sha256(prev_hash + canonical_json(snapshot))
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
from typing import Any

from sqlmodel import Session, select

from app.db import audit, utcnow
from app.models import (
    Ambiguity,
    Claim,
    Handover,
    HandoverVersion,
    PlanItem,
)
from app.verify import generate_scorecard

logger = logging.getLogger("relayops.handover.versions")


def canonical_json(data: Any) -> str:
    """Produce deterministic, whitespace-normalized, sorted JSON for cryptographic hashing."""

    def _default(obj: Any) -> Any:
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        return str(obj)

    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=_default)


def compute_version_hash(prev_hash: str, snapshot: dict[str, Any]) -> str:
    """Compute SHA-256 hash chaining previous version's hash with canonical snapshot JSON."""
    canon_str = canonical_json(snapshot)
    return hashlib.sha256((prev_hash + canon_str).encode("utf-8")).hexdigest()


def create_snapshot(
    session: Session,
    handover_id: str,
    *,
    actor_id: str | None = None,
    reason: str = "",
) -> HandoverVersion:
    """Freeze all current claims, ambiguities, plan items, and scorecard into a HandoverVersion."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise ValueError(f"Handover {handover_id} not found")

    # Fetch all current handover artifacts
    claims = session.exec(
        select(Claim).where(Claim.handover_id == handover_id).order_by(Claim.order_index, Claim.id)
    ).all()
    ambiguities = session.exec(
        select(Ambiguity).where(Ambiguity.handover_id == handover_id).order_by(Ambiguity.id)
    ).all()
    plan_items = session.exec(
        select(PlanItem).where(PlanItem.handover_id == handover_id).order_by(PlanItem.day_bucket, PlanItem.id)
    ).all()

    # Generate current verification scorecard
    scorecard = generate_scorecard(handover.project_id, session, claims=claims)

    # Determine next version and previous hash
    last_v = session.exec(
        select(HandoverVersion)
        .where(HandoverVersion.handover_id == handover_id)
        .order_by(HandoverVersion.version.desc())
        .limit(1)
    ).first()

    next_version = (last_v.version + 1) if last_v else 1
    prev_hash = last_v.hash if last_v else ""

    snapshot: dict[str, Any] = {
        "handover_id": handover_id,
        "project_id": handover.project_id,
        "version": next_version,
        "created_at": utcnow().isoformat(),
        "created_by": actor_id,
        "reason": reason,
        "claims": [c.model_dump(mode="json") for c in claims],
        "ambiguities": [a.model_dump(mode="json") for a in ambiguities],
        "plan_items": [p.model_dump(mode="json") for p in plan_items],
        "scorecard": scorecard.model_dump(mode="json"),
    }

    # Normalize snapshot so SQLite JSON serialization preserves exact roundtrip
    clean_snapshot = json.loads(canonical_json(snapshot))
    version_hash = compute_version_hash(prev_hash, clean_snapshot)

    hv = HandoverVersion(
        handover_id=handover_id,
        version=next_version,
        snapshot=clean_snapshot,
        prev_hash=prev_hash,
        hash=version_hash,
        created_by=actor_id,
        reason=reason,
    )
    session.add(hv)

    handover.current_version = next_version
    if handover.status == "draft":
        handover.status = "in_review"
    handover.updated_at = utcnow()
    session.add(handover)

    # Write audit log
    audit(
        session,
        actor_id=actor_id,
        action="snapshot_created",
        target_type="handover_version",
        target_id=hv.id,
        payload={
            "handover_id": handover_id,
            "version": next_version,
            "hash": version_hash,
            "claims_count": len(claims),
            "reason": reason,
        },
    )

    session.commit()
    session.refresh(hv)
    logger.info(
        "Created HandoverVersion v%d (%s) for handover %s",
        next_version,
        version_hash[:8],
        handover_id,
    )
    return hv


def compute_word_diff(text1: str, text2: str) -> list[dict[str, str]]:
    """Compute word-level diff tokens between two strings."""
    if text1 == text2:
        return [{"type": "unchanged", "text": text1}] if text1 else []

    words1 = text1.split()
    words2 = text2.split()
    matcher = difflib.SequenceMatcher(None, words1, words2)
    diff_tokens: list[dict[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            diff_tokens.append({"type": "unchanged", "text": " ".join(words1[i1:i2])})
        elif tag == "delete":
            diff_tokens.append({"type": "removed", "text": " ".join(words1[i1:i2])})
        elif tag == "insert":
            diff_tokens.append({"type": "added", "text": " ".join(words2[j1:j2])})
        elif tag == "replace":
            diff_tokens.append({"type": "removed", "text": " ".join(words1[i1:i2])})
            diff_tokens.append({"type": "added", "text": " ".join(words2[j1:j2])})

    return diff_tokens


def diff_versions(
    v1: HandoverVersion,
    v2: HandoverVersion,
) -> dict[str, Any]:
    """Compute structured diff between two handover snapshots (added/removed/changed claims)."""
    s1 = v1.snapshot or {}
    s2 = v2.snapshot or {}

    c1_map = {c["id"]: c for c in s1.get("claims", []) if isinstance(c, dict) and "id" in c}
    c2_map = {c["id"]: c for c in s2.get("claims", []) if isinstance(c, dict) and "id" in c}

    added_claims: list[dict[str, Any]] = []
    removed_claims: list[dict[str, Any]] = []
    changed_claims: list[dict[str, Any]] = []

    # Added claims
    for cid, c2 in c2_map.items():
        if cid not in c1_map:
            added_claims.append(c2)

    # Removed claims
    for cid, c1 in c1_map.items():
        if cid not in c2_map:
            removed_claims.append(c1)

    # Changed claims
    for cid, c1 in c1_map.items():
        if cid in c2_map:
            c2 = c2_map[cid]
            changes: dict[str, Any] = {}
            if c1.get("text") != c2.get("text"):
                changes["text"] = {
                    "from": c1.get("text"),
                    "to": c2.get("text"),
                    "word_diff": compute_word_diff(c1.get("text") or "", c2.get("text") or ""),
                }
            if c1.get("status") != c2.get("status"):
                changes["status"] = {"from": c1.get("status"), "to": c2.get("status")}
            if c1.get("section") != c2.get("section"):
                changes["section"] = {"from": c1.get("section"), "to": c2.get("section")}
            if c1.get("kind") != c2.get("kind"):
                changes["kind"] = {"from": c1.get("kind"), "to": c2.get("kind")}
            if c1.get("evidence") != c2.get("evidence"):
                changes["evidence"] = {"from": c1.get("evidence"), "to": c2.get("evidence")}

            if changes:
                changed_claims.append(
                    {
                        "id": cid,
                        "claim_id": cid,
                        "before": c1,
                        "after": c2,
                        "changes": changes,
                    }
                )

    # Ambiguities diff
    a1_map = {a["id"]: a for a in s1.get("ambiguities", []) if isinstance(a, dict) and "id" in a}
    a2_map = {a["id"]: a for a in s2.get("ambiguities", []) if isinstance(a, dict) and "id" in a}

    added_ambs = [a2 for aid, a2 in a2_map.items() if aid not in a1_map]
    resolved_ambs = [
        a2
        for aid, a2 in a2_map.items()
        if aid in a1_map and a1_map[aid].get("status") == "open" and a2.get("status") != "open"
    ]

    return {
        "handover_id": v1.handover_id,
        "from_version": v1.version,
        "to_version": v2.version,
        "from_hash": v1.hash,
        "to_hash": v2.hash,
        "claims": {
            "added": added_claims,
            "removed": removed_claims,
            "changed": changed_claims,
            "summary": {
                "added_count": len(added_claims),
                "removed_count": len(removed_claims),
                "changed_count": len(changed_claims),
            },
        },
        "ambiguities": {
            "added": added_ambs,
            "resolved": resolved_ambs,
            "summary": {
                "added_count": len(added_ambs),
                "resolved_count": len(resolved_ambs),
            },
        },
    }
