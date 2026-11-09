"""Citations validation, substring verification, and evidence binding.

Enforces RelayOps Non-negotiable rule #1:
Every claim shown to a successor must have >= 1 evidence link to a real artifact
(source_uri + snippet). Claims with zero valid evidence are rejected by the validator
and never persisted as "verified". Paraphrased snippets are repaired to real substrings
using sliding-window fuzzy matching.
"""

from __future__ import annotations

import difflib
import logging
import re
from typing import Any

from sqlmodel import Session, select

from app.models import Artifact, Claim, Handover

logger = logging.getLogger("relayops.verify.citations")


def find_best_span(
    text: str,
    query: str,
    threshold: float = 0.85,
) -> tuple[int, int, str, float] | None:
    """Locate the best matching substring in text for a given query snippet.

    Returns:
        (char_start, char_end, real_snippet, match_ratio) or None if no match >= threshold.
    """
    if not text or not query:
        return None

    norm_query = " ".join(query.split())
    if not norm_query:
        return None

    # 1. Exact case-sensitive match
    idx = text.find(query)
    if idx != -1:
        return (idx, idx + len(query), query, 1.0)

    # 2. Case-insensitive exact match
    idx_lower = text.lower().find(query.lower())
    if idx_lower != -1:
        real_snippet = text[idx_lower : idx_lower + len(query)]
        return (idx_lower, idx_lower + len(query), real_snippet, 1.0)

    # 3. Normalized whitespace exact match
    # Find matching regex pattern accounting for varying whitespaces
    pattern = r"\s+".join(re.escape(w) for w in norm_query.split())
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return (match.start(), match.end(), text[match.start() : match.end()], 1.0)

    # 4. Sliding-window fuzzy matching across words
    words = text.split()
    q_words = norm_query.split()
    q_len = len(q_words)
    if q_len == 0 or len(words) == 0:
        return None

    # Candidate window sizes around the query length
    min_w = max(1, q_len - 3)
    max_w = min(len(words), q_len + 4)
    window_sizes = sorted({q_len, q_len - 1, q_len + 1, q_len - 2, q_len + 2, min_w, max_w})

    best_ratio = 0.0
    best_chunk = ""

    for w_size in window_sizes:
        if w_size <= 0 or w_size > len(words):
            continue
        for i in range(0, len(words) - w_size + 1):
            chunk = " ".join(words[i : i + w_size])
            r = difflib.SequenceMatcher(None, norm_query.lower(), chunk.lower()).ratio()
            if r > best_ratio:
                best_ratio = r
                best_chunk = chunk
                if r >= 0.98:
                    break
        if best_ratio >= 0.98:
            break

    if best_ratio >= threshold and best_chunk:
        chunk_pattern = r"\s+".join(re.escape(w) for w in best_chunk.split())
        m = re.search(chunk_pattern, text)
        if m:
            return (m.start(), m.end(), text[m.start() : m.end()], best_ratio)
        idx_c = text.find(best_chunk)
        if idx_c != -1:
            return (idx_c, idx_c + len(best_chunk), best_chunk, best_ratio)

    return None


def compute_deep_link(
    artifact: Artifact,
    char_start: int = 0,
    char_end: int = 0,
    sub_id: str | None = None,
) -> str:
    """Compute a deterministic permalink/deep-link for an artifact."""
    uri = artifact.source_uri or ""
    kind = (artifact.kind or "").lower()

    if kind == "commit":
        if "github.com" in uri:
            return uri
        return f"https://github.com/payflow/payflow/commit/{artifact.external_id}"

    if kind == "pull_request":
        if "github.com" in uri and "/pull/" in uri:
            return uri
        clean_num = artifact.external_id.replace("PR-", "")
        return f"https://github.com/payflow/payflow/pull/{clean_num}"

    if kind == "issue":
        if uri.startswith("http"):
            return uri
        return f"https://jira.payflow.internal/browse/{artifact.external_id}"

    if kind in ("adr_doc", "meeting_note", "runbook", "code_file"):
        clean_uri = uri.split("#")[0]
        return f"{clean_uri}#offset={char_start}:{char_end}"

    if kind == "chat_thread":
        clean_uri = uri.split("#")[0]
        target = sub_id or f"offset={char_start}:{char_end}"
        return f"{clean_uri}#{target}"

    # Default fallback
    clean_uri = uri.split("#")[0]
    return f"{clean_uri}#offset={char_start}:{char_end}"


def _find_artifact(
    eid: str,
    project_id: str,
    session: Session,
) -> tuple[Artifact | None, str | None]:
    """Find an artifact by ID, external_id, PR prefix, or nested message ID."""
    clean_eid = eid.replace("PR-", "")
    target_pr = f"PR-{eid}"

    # Direct query
    art = session.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            (Artifact.id == eid)
            | (Artifact.external_id == eid)
            | (Artifact.external_id == clean_eid)
            | (Artifact.external_id == target_pr),
        )
    ).first()

    if art:
        return art, None

    # Check for chat thread message ID
    if eid.startswith("msg_"):
        threads = session.exec(
            select(Artifact).where(
                Artifact.project_id == project_id,
                Artifact.kind == "chat_thread",
            )
        ).all()
        for t in threads:
            if t.meta and isinstance(t.meta, dict):
                for m in t.meta.get("messages", []):
                    if isinstance(m, dict) and m.get("message_id") == eid:
                        return t, eid

    return None, None


def bind_and_validate(
    claim: Claim,
    session: Session,
    project_id: str | None = None,
) -> Claim:
    """Validate all citations for a claim against the project's artifact database.

    - Every evidence_id must exist in the artifact table for this project.
    - Snippets must match real substrings of artifact.body_redacted (with fuzzy repair if paraphrased).
    - Source deep links are computed.
    - Sensitivity is set to the maximum sensitivity of all supporting artifacts.
    - Claims with zero valid evidence are marked as rejected with reason="no_valid_evidence".
    """
    proj_id = project_id or claim.project_id
    if not proj_id and claim.handover_id:
        handover = session.get(Handover, claim.handover_id)
        if handover:
            proj_id = handover.project_id

    if not proj_id:
        claim.status = "rejected"
        claim.rejected_reason = "no_valid_evidence"
        claim.evidence = []
        return claim

    raw_evidence_list = claim.evidence or []
    valid_evidence: list[dict[str, Any]] = []

    for item in raw_evidence_list:
        eid = ""
        snippet_candidate = ""

        if isinstance(item, dict):
            eid = str(item.get("artifact_id") or item.get("external_id") or item.get("id") or "").strip()
            snippet_candidate = str(item.get("snippet") or "").strip()
        elif isinstance(item, str):
            eid = item.strip()

        if not eid:
            continue

        artifact, sub_msg_id = _find_artifact(eid, proj_id, session)
        if not artifact:
            logger.warning("Evidence artifact '%s' not found for project %s", eid, proj_id)
            continue

        # Validate or locate real snippet in artifact.title and artifact.body_redacted
        body = artifact.body_redacted or ""
        search_text = f"{artifact.title}\n\n{body}" if artifact.title else body
        matched_span = None

        if snippet_candidate:
            matched_span = find_best_span(search_text, snippet_candidate, threshold=0.80)

        # If snippet was empty or fuzzy match failed, try matching claim text
        if not matched_span and claim.text:
            matched_span = find_best_span(search_text, claim.text, threshold=0.75)

        # If still no match and artifact has messages, search inside the specific message
        if not matched_span and sub_msg_id and artifact.meta:
            for m in artifact.meta.get("messages", []):
                if m.get("message_id") == sub_msg_id:
                    start = m.get("char_start", 0)
                    end = m.get("char_end", len(body))
                    msg_body = m.get("text") or m.get("body") or (body[start:end] if 0 <= start < end <= len(body) else "")
                    if msg_body:
                        matched_span = find_best_span(search_text, msg_body, threshold=0.70) or (start, end, msg_body.strip(), 1.0)
                    break

        if not matched_span:
            logger.info("Snippet validation failed for evidence '%s'", eid)
            continue

        char_start, char_end, real_snippet, _ratio = matched_span
        source_uri = compute_deep_link(artifact, char_start, char_end, sub_msg_id)

        ev_entry: dict[str, Any] = {
            "artifact_id": artifact.id,
            "external_id": artifact.external_id,
            "source_uri": source_uri,
            "snippet": real_snippet,
            "char_start": char_start,
            "char_end": char_end,
            "sensitivity": int(artifact.sensitivity or 0),
            "authority": float(artifact.authority or 0.5),
        }
        if isinstance(item, dict):
            if "node_id" in item:
                ev_entry["node_id"] = item["node_id"]
            if "node_key" in item:
                ev_entry["node_key"] = item["node_key"]

        valid_evidence.append(ev_entry)

    if not valid_evidence:
        claim.status = "rejected"
        claim.rejected_reason = "no_valid_evidence"
        claim.evidence = []
    else:
        claim.evidence = valid_evidence
        claim.sensitivity = max(e["sensitivity"] for e in valid_evidence)
        if claim.status in ("draft", "rejected"):
            claim.status = "accepted"
            claim.rejected_reason = None

    session.add(claim)
    return claim


def validate_claims_batch(
    claims: list[Claim],
    session: Session,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Validate a batch of claims and report acceptance/rejection statistics."""
    accepted = 0
    rejected = 0

    for claim in claims:
        bind_and_validate(claim, session, project_id)
        if claim.status == "rejected":
            rejected += 1
        else:
            accepted += 1

    session.commit()
    return {
        "total": len(claims),
        "accepted": accepted,
        "rejected": rejected,
        "rejection_rate": (rejected / max(len(claims), 1)),
    }
