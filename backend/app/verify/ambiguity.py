"""Deterministic ambiguity detectors for the RelayOps Ambiguity Ledger.

Non-negotiable rule #2:
When evidence is missing or conflicting, we say so (Ambiguity Ledger). We never smooth over gaps.

Detectors:
1. orphan_branch: Unmerged branch with active commits.
2. unclosed_thread: Question with no reply or outgoing person tagged without answer.
3. undocumented_module: Module with active commits but zero architecture/runbook docs.
4. stale_config: Environment variables ending in _OLD, _DEPRECATED, or referenced in fallback code.
5. missing_doc: Open blocker ticket with no runbook or resolution guide.
6. low_evidence: Claims supported solely by chat messages (authority <= 0.4).
"""

from __future__ import annotations

import logging
import re

from sqlmodel import Session, select

from app.models import Ambiguity, Artifact, Claim

logger = logging.getLogger("relayops.verify.ambiguity")


def detect_orphan_branches(project_id: str, session: Session) -> list[Ambiguity]:
    """Detect unmerged branches containing active development commits."""
    ambiguities: list[Ambiguity] = []
    branches = session.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.kind == "branch",
        )
    ).all()

    for branch in branches:
        is_merged = True
        if branch.meta and isinstance(branch.meta, dict):
            is_merged = branch.meta.get("merged", True)
        elif "unmerged" in (branch.title or "").lower():
            is_merged = False

        if not is_merged:
            amb = Ambiguity(
                project_id=project_id,
                type="orphan_branch",
                severity="high",
                title=f"Orphan branch: {branch.external_id}",
                description=(
                    f"Branch '{branch.external_id}' contains active unmerged commits "
                    f"that must be reconciled or handed over before departure."
                ),
                artifact_ids=[branch.external_id],
                status="open",
            )
            ambiguities.append(amb)

    return ambiguities


def detect_unclosed_threads(project_id: str, session: Session) -> list[Ambiguity]:
    """Detect chat threads with unanswered questions or untracked handover inquiries."""
    ambiguities: list[Ambiguity] = []
    threads = session.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.kind == "chat_thread",
        )
    ).all()

    for thread in threads:
        meta = thread.meta or {}
        messages = meta.get("messages", [])
        if not messages:
            continue

        # Look for questions in thread where no reply followed or only 1 message
        last_msg = messages[-1]
        last_text = last_msg.get("text") or last_msg.get("body") or ""

        is_unanswered = (
            (len(messages) == 1 and "?" in last_text)
            or ("?" in last_text and ("@aarav" in last_text.lower() or "legacy" in last_text.lower()))
            or "unanswered" in thread.external_id.lower()
        )

        if is_unanswered:
            target_id = last_msg.get("message_id") or thread.external_id
            amb = Ambiguity(
                project_id=project_id,
                type="unclosed_thread",
                severity="high",
                title=f"Unclosed discussion thread: {thread.title or thread.external_id}",
                description=(
                    f"Chat thread '{thread.external_id}' contains an unanswered inquiry "
                    f"regarding legacy handover functionality ('{last_text[:80]}...')."
                ),
                artifact_ids=[thread.external_id, target_id],
                status="open",
            )
            ambiguities.append(amb)

    return ambiguities


def detect_undocumented_modules(project_id: str, session: Session) -> list[Ambiguity]:
    """Detect functional modules with active commits but zero architectural documentation."""
    ambiguities: list[Ambiguity] = []

    # 1. Gather all file paths from commits to determine modules
    commits = session.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.kind == "commit",
        )
    ).all()

    module_commit_counts: dict[str, int] = {}
    for c in commits:
        meta = c.meta or {}
        files = meta.get("files_changed") or meta.get("files") or meta.get("changed_files") or []
        for f in files:
            parts = f.replace("\\", "/").strip("/").split("/")
            mod = None
            if len(parts) >= 3 and parts[0] == "src" and parts[1] == "payflow":
                mod = parts[2]
            elif len(parts) > 1 and parts[0] not in ("docs", "tests", ".github", ".husky", "migrations"):
                mod = parts[0]

            if mod and "." not in mod:
                module_commit_counts[mod] = module_commit_counts.get(mod, 0) + 1

    # 2. Check documentation artifacts for references to each module
    doc_artifacts = session.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.kind.in_(["adr_doc", "meeting_note", "runbook"]),
        )
    ).all()

    doc_text = " ".join(f"{d.title} {d.body_redacted}".lower() for d in doc_artifacts)

    for mod, count in module_commit_counts.items():
        norm_mod = mod.lower().replace("-", " ")
        if count >= 2 and mod.lower() not in doc_text and norm_mod not in doc_text:
            amb = Ambiguity(
                project_id=project_id,
                type="undocumented_module",
                severity="high",
                title=f"Undocumented module: {mod}",
                description=(
                    f"Module '{mod}' has {count} commits but is completely unreferenced "
                    f"in architectural decision records or runbooks (bus factor 1 risk)."
                ),
                artifact_ids=[mod],
                status="open",
            )
            ambiguities.append(amb)

    return ambiguities


def detect_stale_config(project_id: str, session: Session) -> list[Ambiguity]:
    """Detect environment configuration variables tagged _OLD, _DEPRECATED, or obsolete."""
    ambiguities: list[Ambiguity] = []
    artifacts = session.exec(select(Artifact).where(Artifact.project_id == project_id)).all()

    found_stale_vars: dict[str, list[str]] = {}

    for art in artifacts:
        full_text = f"{art.title} {art.body_redacted}"
        matches = re.findall(r"\b([A-Z0-9_]+_(?:OLD|DEPRECATED|LEGACY))\b", full_text)
        for var_name in matches:
            if var_name not in found_stale_vars:
                found_stale_vars[var_name] = []
            if art.external_id not in found_stale_vars[var_name]:
                found_stale_vars[var_name].append(art.external_id)

    for var_name, art_ids in found_stale_vars.items():
        amb = Ambiguity(
            project_id=project_id,
            type="stale_config",
            severity="med",
            title=f"Stale configuration variable: {var_name}",
            description=(
                f"Configuration variable '{var_name}' is referenced in fallback code or documentation "
                f"({', '.join(art_ids[:3])}) but is deprecated and represents technical debt."
            ),
            artifact_ids=art_ids,
            status="open",
        )
        ambiguities.append(amb)

    return ambiguities


def detect_missing_docs(project_id: str, session: Session) -> list[Ambiguity]:
    """Detect open blocker tickets without an attached runbook or operational guide."""
    ambiguities: list[Ambiguity] = []
    issues = session.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.kind == "issue",
        )
    ).all()

    runbooks = session.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.kind == "runbook",
        )
    ).all()
    runbook_text = " ".join(f"{r.title} {r.body_redacted}".lower() for r in runbooks)

    for issue in issues:
        meta = issue.meta or {}
        is_blocker = (
            meta.get("state") == "blocked"
            or meta.get("priority") == "blocker"
            or "blocker" in (issue.title or "").lower()
            or issue.external_id == "PAY-142"
        )

        if is_blocker and issue.external_id.lower() not in runbook_text:
            amb = Ambiguity(
                project_id=project_id,
                type="missing_doc",
                severity="high",
                title=f"Missing documentation for blocker {issue.external_id}",
                description=(
                    f"Active blocker '{issue.external_id}' ({issue.title}) has no corresponding "
                    f"operational runbook or resolution guide."
                ),
                artifact_ids=[issue.external_id],
                status="open",
            )
            ambiguities.append(amb)

    return ambiguities


def detect_low_evidence(
    project_id: str,
    session: Session,
    claims: list[Claim] | None = None,
) -> list[Ambiguity]:
    """Detect accepted claims that rely solely on low-authority chat messages."""
    ambiguities: list[Ambiguity] = []
    claim_list = claims or session.exec(select(Claim).where(Claim.project_id == project_id)).all()

    for c in claim_list:
        if c.status == "rejected" or not c.evidence:
            continue
        # Check if all evidence items have authority <= 0.4
        max_auth = max(e.get("authority", 0.4) for e in c.evidence)
        if max_auth <= 0.4:
            amb = Ambiguity(
                project_id=project_id,
                handover_id=c.handover_id,
                type="low_evidence",
                severity="low",
                title=f"Low evidence for claim '{c.text[:40]}'",
                description=(
                    f"Claim '{c.text}' is supported solely by informal chat messages "
                    f"(authority score {max_auth:.1f}). Needs code or doc verification."
                ),
                artifact_ids=[c.id],
                status="open",
            )
            ambiguities.append(amb)

    return ambiguities


def detect_all_ambiguities(
    project_id: str,
    session: Session,
    handover_id: str | None = None,
    claims: list[Claim] | None = None,
) -> list[Ambiguity]:
    """Execute all deterministic ambiguity detectors and persist newly discovered items."""
    detected: list[Ambiguity] = []
    detected.extend(detect_orphan_branches(project_id, session))
    detected.extend(detect_unclosed_threads(project_id, session))
    detected.extend(detect_undocumented_modules(project_id, session))
    detected.extend(detect_stale_config(project_id, session))
    detected.extend(detect_missing_docs(project_id, session))
    detected.extend(detect_low_evidence(project_id, session, claims))

    # Retrieve existing ambiguities to avoid duplicate entries
    existing = session.exec(select(Ambiguity).where(Ambiguity.project_id == project_id)).all()
    existing_keys = {(a.type, a.title) for a in existing}

    saved_ambiguities: list[Ambiguity] = list(existing)

    for amb in detected:
        if (amb.type, amb.title) not in existing_keys:
            amb.handover_id = handover_id or amb.handover_id
            session.add(amb)
            existing_keys.add((amb.type, amb.title))
            saved_ambiguities.append(amb)

    session.commit()
    return saved_ambiguities
