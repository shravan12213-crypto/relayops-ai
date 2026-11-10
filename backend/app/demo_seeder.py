"""Comprehensive Demo Data Seeder for RelayOps.

Populates multi-project dummy data across all demo modes:
1. Projects: PayFlow (core), CloudMesh Gateway (edge), AuthCore Identity (auth)
2. All 5 demo personas mapped to appropriate project roles & clearances
3. Handovers in ALL 4 workflow states:
   - in_review (hero handover with dual sign-off pending, verified & review claims, ambiguities)
   - signed (tamper-sealed with HMAC signatures from both outgoing and lead)
   - delivered (delivered to successor Kabir, signed receipts, and active Copilot Q&A history)
   - draft (newly ingested claims awaiting review)
4. Realistic Claims across all 9 kinds with artifact evidence snippets
5. Ambiguities across all categories (conflict, orphan_branch, missing_doc, stale_config, etc.)
6. Day 1-30 Onboarding Plan items with status tracking
7. Tamper-evident cryptographic audit log chain
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlmodel import Session, select

from app.auth import hash_password
from app.config import get_settings
from app.db import audit, utcnow
from app.handover.signoff import compute_signoff_hmac
from app.handover.versions import compute_version_hash
from app.models import (
    Ambiguity,
    Artifact,
    ChatMessage,
    ChatSession,
    Claim,
    Handover,
    HandoverVersion,
    PlanItem,
    Project,
    ProjectMember,
    Receipt,
    RedactionEvent,
    Signoff,
    User,
)

logger = logging.getLogger("relayops.demo_seeder")


def seed_demo_data(session: Session) -> dict[str, Any]:
    """Seed comprehensive dummy data for all RelayOps demo modes."""
    settings = get_settings()
    now = utcnow()

    # -------------------------------------------------------------------------
    # 1. Ensure the 5 canonical demo users exist
    # -------------------------------------------------------------------------
    demo_users_spec = [
        ("aarav@payflow.dev", "Aarav Kulkarni", "outgoing", 2),
        ("meera@payflow.dev", "Meera Patel", "lead", 3),
        ("kabir@payflow.dev", "Kabir Sharma", "successor", 1),
        ("sana@payflow.dev", "Sana Chen", "auditor", 1),
        ("dev@payflow.dev", "Dev Mukherjee", "contractor", 1),
    ]

    users: dict[str, User] = {}
    for email, name, role, clearance in demo_users_spec:
        user = session.exec(select(User).where(User.email == email.lower())).first()
        if not user:
            user = User(
                email=email.lower(),
                name=name,
                password_hash=hash_password("password123"),
                role=role,
                clearance=clearance,
                is_active=True,
            )
            session.add(user)
            session.flush()
        users[email] = user

    aarav = users["aarav@payflow.dev"]
    meera = users["meera@payflow.dev"]
    kabir = users["kabir@payflow.dev"]
    sana = users["sana@payflow.dev"]
    dev = users["dev@payflow.dev"]

    # -------------------------------------------------------------------------
    # 2. Multi-Project Setup
    # -------------------------------------------------------------------------
    projects_spec = [
        (
            "payflow",
            "PayFlow",
            "Payment webhook infrastructure & transaction ledger with idempotency engine.",
            "https://github.com/payflow/payflow",
        ),
        (
            "cloudmesh-gateway",
            "CloudMesh Gateway",
            "Zero-trust Envoy edge gateway, dynamic mTLS routing, and distributed rate limiting.",
            "https://github.com/payflow/cloudmesh-gateway",
        ),
        (
            "authcore-id",
            "AuthCore Identity",
            "Distributed OAuth2/OIDC token authority, PKCE session exchange, and RBAC policies.",
            "https://github.com/payflow/authcore-id",
        ),
    ]

    projects: dict[str, Project] = {}
    for slug, name, desc, repo in projects_spec:
        proj = session.exec(select(Project).where(Project.slug == slug)).first()
        if not proj:
            proj = Project(slug=slug, name=name, description=desc, repo_url=repo, status="active")
            session.add(proj)
            session.flush()
        projects[slug] = proj

        # Associate all demo personas with membership
        for u in [aarav, meera, kabir, sana, dev]:
            pm = session.exec(
                select(ProjectMember).where(
                    ProjectMember.project_id == proj.id, ProjectMember.user_id == u.id
                )
            ).first()
            if not pm:
                prole = "lead" if u.role == "lead" else ("auditor" if u.role == "auditor" else "contributor")
                session.add(ProjectMember(project_id=proj.id, user_id=u.id, project_role=prole))
    session.flush()

    payflow = projects["payflow"]
    cloudmesh = projects["cloudmesh-gateway"]
    authcore = projects["authcore-id"]

    # Grab any existing real artifacts for PayFlow to attach evidence snippets
    pf_artifacts = session.exec(select(Artifact).where(Artifact.project_id == payflow.id)).all()
    art_map = {a.source_uri: a for a in pf_artifacts}
    art_list = list(pf_artifacts)

    def _evidence(
        source_uri: str, snippet: str, char_start: int = 0, char_end: int = 100
    ) -> list[dict[str, Any]]:
        matched = art_map.get(source_uri)
        art_id = matched.id if matched else (art_list[0].id if art_list else "art_seed_fallback")
        return [
            {
                "artifact_id": art_id,
                "source_uri": source_uri,
                "snippet": snippet,
                "char_start": char_start,
                "char_end": char_end,
            }
        ]

    # -------------------------------------------------------------------------
    # 3. Handover 1: PayFlow Webhook Reliability (Status: IN_REVIEW - Hero)
    # -------------------------------------------------------------------------
    h1 = session.exec(
        select(Handover).where(
            Handover.project_id == payflow.id,
            Handover.notes == "PayFlow Webhook Reliability & Transaction Ledger",
        )
    ).first()

    if not h1:
        h1 = Handover(
            project_id=payflow.id,
            outgoing_user_id=aarav.id,
            successor_user_id=kabir.id,
            lead_user_id=meera.id,
            status="in_review",
            current_version=1,
            due_date=now + timedelta(days=14),
            notes="PayFlow Webhook Reliability & Transaction Ledger",
        )
        session.add(h1)
        session.flush()
    else:
        h1.status = "in_review"
        session.add(h1)
        session.flush()

    # Claims for Handover 1
    h1_claims_spec = [
        (
            "architecture_decision",
            "Stateless JWT tokens adopted for auth (supersedes Redis session caching from ADR-003).",
            "accepted",
            0.96,
            1,
            "docs/ADR-003-session-caching.md",
            "ADR-003 proposed Redis session caching; superseded by PR #89 with stateless JWT tokens.",
        ),
        (
            "architecture_decision",
            "PostgreSQL 16 selected for ledger transaction store (supersedes MongoDB evaluation in RFC-007).",
            "accepted",
            0.95,
            1,
            "docs/RFC-007-mongodb-eval.md",
            "RFC-007 evaluated MongoDB document store; PR #42 migrated ledger schema to PostgreSQL 16.",
        ),
        (
            "runbook",
            "Dead-Letter Queue (DLQ) replay: trigger /api/v1/admin/replay-dlq with idempotency header.",
            "accepted",
            0.98,
            1,
            "docs/runbook-webhooks.md",
            "Execute curl -X POST /api/v1/admin/replay-dlq -H 'X-Idempotency-Key: ...' to drain DLQ.",
        ),
        (
            "blocker",
            "PAY-142: AcquirerCorp sandbox credential rotation blocked on external vendor contact.",
            "needs_review",
            0.88,
            2,
            "jira://PAY-142",
            "PAY-142: Waiting on vendor escalation for sandbox TLS certificates before go-live.",
        ),
        (
            "ownership",
            "Aarav Kulkarni is sole codeowner of ledger-sync batch reconciliation service.",
            "accepted",
            0.94,
            1,
            "git://commits/c1a0110000000000000000000000000000000060",
            "Author: Aarav Kulkarni <aarav@payflow.dev> - Add ledger-sync batch processor.",
        ),
        (
            "risk",
            "Webhook signature key rotation occurs on Dec 15; zero-downtime requires dual-key validation.",
            "accepted",
            0.92,
            2,
            "docs/runbook-webhooks.md",
            "During key rotation, the dispatcher must accept both old and new HMAC secrets for 72 hours.",
        ),
        (
            "dependency",
            "Requires Redis 7.2 cluster for distributed webhook rate limiting (sliding window algorithm).",
            "accepted",
            0.91,
            1,
            "docs/architecture-overview.md",
            "Redis 7.2 cluster cluster_mode=enabled required for atomic sliding-window increment.",
        ),
        (
            "open_work",
            "Complete idempotency deduplication on partial refunds (branch: hotfix/idempotency-keys).",
            "needs_review",
            0.85,
            1,
            "git://branches/hotfix/idempotency-keys",
            "hotfix/idempotency-keys contains 4 commits adding refund deduplication logic.",
        ),
        (
            "contact",
            "Vendor escalation: David Vance (david.vance@acquirercorp.com), Head of Integration Engineering.",
            "accepted",
            0.97,
            2,
            "slack://leads-private/msg_leads_vendor_01",
            "Escalation contact for AcquirerCorp production outages is David Vance.",
        ),
        (
            "credential_ref",
            "Acquirer webhook secret in AWS Secrets Manager: arn:aws:secretsmanager:...:acquirer-secret.",
            "accepted",
            0.99,
            3,
            "docs/security-runbook.md",
            "Do not hardcode webhook secret; retrieve from AWS Secrets Manager.",
        ),
        (
            "runbook",
            "Database failover drill: execute pg_ctl promote on replica db-read-02 and reset pool.",
            "accepted",
            0.93,
            1,
            "docs/runbook-database.md",
            "Database failover runbook: run scripts/failover.sh with active maintenance token.",
        ),
        (
            "architecture_decision",
            "Webhook payload encryption enabled using AES-256-GCM before persistent staging.",
            "needs_review",
            0.89,
            2,
            "docs/ADR-004-payload-encryption.md",
            "ADR-004 specifies AES-256-GCM envelope encryption for incoming webhook bodies.",
        ),
    ]

    for idx, (kind, text, st, conf, sens, uri, snip) in enumerate(h1_claims_spec):
        cl = session.exec(select(Claim).where(Claim.handover_id == h1.id, Claim.text == text)).first()
        if not cl:
            cl = Claim(
                project_id=payflow.id,
                handover_id=h1.id,
                section="Core Webhook Architecture",
                kind=kind,
                text=text,
                status=st,
                confidence=conf,
                sensitivity=sens,
                evidence=_evidence(uri, snip),
                origin="llm",
                order_index=idx,
            )
            session.add(cl)
    session.flush()

    # Ambiguities for Handover 1
    h1_ambs_spec = [
        (
            "conflict",
            "high",
            "AcquirerCorp Rate Limit Disagreement (100/min vs 500/min)",
            "Slack messages on Oct 18 disagree on the AcquirerCorp rate limit with no code resolution.",
            "open",
            None,
        ),
        (
            "conflict",
            "high",
            "Webhook retry limit contradiction between runbook (3) and code (5)",
            "Runbook claims retry limit is 3; PR #65 code sets max_attempts to 5. Code wins by authority.",
            "open",
            None,
        ),
        (
            "orphan_branch",
            "med",
            "Two unmerged branches with active development logic",
            "feature/webhook-retry-v2 and hotfix/idempotency-keys contain unmerged critical business logic.",
            "open",
            None,
        ),
        (
            "undocumented_module",
            "high",
            "Module ledger-sync has no documentation and single author (bus factor risk)",
            "ledger-sync module has commits from Aarav and zero architecture docs or secondary reviewers.",
            "open",
            None,
        ),
        (
            "stale_config",
            "low",
            "Stale configuration variable reference STRIPE_WEBHOOK_SECRET_OLD",
            "STRIPE_WEBHOOK_SECRET_OLD is still referenced in runbook-webhooks.md and fallback code.",
            "resolved",
            "Removed deprecated secret reference in commit e7b1a2 and rotated active keys.",
        ),
        (
            "unclosed_thread",
            "med",
            "Unclosed Slack thread with unanswered handover question to Aarav",
            "Slack thread in #backend-dev regarding legacy v1 HMAC verification was never answered by Aarav.",
            "open",
            None,
        ),
    ]

    for atype, sev, title, desc, ast, res in h1_ambs_spec:
        amb = session.exec(
            select(Ambiguity).where(Ambiguity.handover_id == h1.id, Ambiguity.title == title)
        ).first()
        if not amb:
            amb = Ambiguity(
                project_id=payflow.id,
                handover_id=h1.id,
                type=atype,
                severity=sev,
                title=title,
                description=desc,
                artifact_ids=[art_list[0].id if art_list else "art_fallback"],
                status=ast,
                resolution_note=res,
                resolved_by=meera.id if res else None,
            )
            session.add(amb)
    session.flush()

    # Plan Items for Handover 1
    h1_plan_spec = [
        (
            "d1_7",
            "Clone PayFlow repository and verify local webhook replay test suite",
            "high",
            "done",
            "Kabir Sharma",
        ),
        (
            "d1_7",
            "Review ADR-003 and PR #89 explaining stateless JWT transition",
            "high",
            "doing",
            "Kabir Sharma",
        ),
        (
            "d8_14",
            "Shadow Aarav during Friday webhook DLQ drain and inspect retry metrics in Grafana",
            "high",
            "todo",
            "Kabir Sharma",
        ),
        (
            "d8_14",
            "Resolve AcquirerCorp 100/min vs 500/min rate limit discrepancy with David Vance",
            "medium",
            "todo",
            "Kabir Sharma",
        ),
        (
            "d15_30",
            "Merge hotfix/idempotency-keys after reviewing partial refund deduplication tests",
            "medium",
            "todo",
            "Kabir Sharma",
        ),
        (
            "d15_30",
            "Assume primary on-call pager duty rotation for ledger-sync service",
            "high",
            "todo",
            "Kabir Sharma",
        ),
    ]

    for bucket, ptitle, prio, pstatus, assignee in h1_plan_spec:
        pitem = session.exec(
            select(PlanItem).where(PlanItem.handover_id == h1.id, PlanItem.title == ptitle)
        ).first()
        if not pitem:
            pitem = PlanItem(
                handover_id=h1.id,
                day_bucket=bucket,
                title=ptitle,
                priority=prio,
                status=pstatus,
                assignee=assignee,
                description=f"Action item assigned to {assignee} for {bucket} onboarding window.",
            )
            session.add(pitem)
    session.flush()

    # Version 1 Snapshot for Handover 1
    hv1 = session.exec(
        select(HandoverVersion).where(HandoverVersion.handover_id == h1.id, HandoverVersion.version == 1)
    ).first()
    if not hv1:
        snapshot1 = {
            "claims_count": len(h1_claims_spec),
            "handover_notes": h1.notes,
            "status": "in_review",
        }
        hv1_hash = compute_version_hash("", snapshot1)
        hv1 = HandoverVersion(
            handover_id=h1.id,
            version=1,
            snapshot=snapshot1,
            prev_hash="",
            hash=hv1_hash,
            created_by=aarav.id,
            reason="Initial reconstruction from PayFlow seed repository",
        )
        session.add(hv1)
        session.flush()

    # Outgoing Aarav has signed v1; Lead Meera is pending (Dual Sign-off hero condition)
    s1_aarav = session.exec(
        select(Signoff).where(Signoff.handover_id == h1.id, Signoff.user_id == aarav.id)
    ).first()
    if not s1_aarav:
        sig_aarav = compute_signoff_hmac(settings.secret_key, h1.id, 1, hv1.hash, aarav.id, now.isoformat())
        s1_aarav = Signoff(
            handover_id=h1.id,
            version=1,
            user_id=aarav.id,
            role="outgoing",
            signature=sig_aarav,
            signed_at=now - timedelta(hours=2),
            comment="Outgoing author sign-off: verified claim evidence and runbook procedures.",
        )
        session.add(s1_aarav)
        session.flush()

    # -------------------------------------------------------------------------
    # 4. Handover 2: Core Ledger Migration & Compliance (Status: SIGNED)
    # -------------------------------------------------------------------------
    h2 = session.exec(
        select(Handover).where(
            Handover.project_id == payflow.id,
            Handover.notes == "Core Ledger Migration & Audit Compliance",
        )
    ).first()

    if not h2:
        h2 = Handover(
            project_id=payflow.id,
            outgoing_user_id=aarav.id,
            successor_user_id=kabir.id,
            lead_user_id=meera.id,
            status="signed",
            current_version=1,
            due_date=now + timedelta(days=7),
            notes="Core Ledger Migration & Audit Compliance",
        )
        session.add(h2)
        session.flush()
    else:
        h2.status = "signed"
        session.add(h2)
        session.flush()

    # Claims for Handover 2
    h2_claims = [
        (
            "architecture_decision",
            "Double-entry bookkeeping ledger enforced via PostgreSQL CHECK constraints.",
            "accepted",
            0.98,
            1,
        ),
        (
            "runbook",
            "Nightly balance reconciliation job executed via cron at 02:00 UTC.",
            "accepted",
            0.96,
            1,
        ),
        (
            "risk",
            "Transaction isolation level SERIALIZABLE required for settlement journal inserts.",
            "accepted",
            0.94,
            2,
        ),
        (
            "contact",
            "Compliance officer escalation: Sana Chen (sana@payflow.dev) for SOX audit reviews.",
            "accepted",
            0.99,
            1,
        ),
    ]
    for idx, (kind, text, st, conf, sens) in enumerate(h2_claims):
        cl = session.exec(select(Claim).where(Claim.handover_id == h2.id, Claim.text == text)).first()
        if not cl:
            cl = Claim(
                project_id=payflow.id,
                handover_id=h2.id,
                section="Double-Entry Ledger Architecture",
                kind=kind,
                text=text,
                status=st,
                confidence=conf,
                sensitivity=sens,
                evidence=_evidence("docs/runbook-database.md", "PostgreSQL double-entry transaction schema."),
                origin="llm",
                order_index=idx,
            )
            session.add(cl)
    session.flush()

    # Version 1 Snapshot for Handover 2
    hv2 = session.exec(
        select(HandoverVersion).where(HandoverVersion.handover_id == h2.id, HandoverVersion.version == 1)
    ).first()
    if not hv2:
        snapshot2 = {
            "claims_count": len(h2_claims),
            "handover_notes": h2.notes,
            "status": "signed",
        }
        hv2_hash = compute_version_hash("", snapshot2)
        hv2 = HandoverVersion(
            handover_id=h2.id,
            version=1,
            snapshot=snapshot2,
            prev_hash="",
            hash=hv2_hash,
            created_by=aarav.id,
            reason="Tamper-sealed snapshot for Core Ledger Migration",
        )
        session.add(hv2)
        session.flush()

    # Dual sign-offs: both Aarav (outgoing) AND Meera (lead) have signed
    for u, urole, comment in [
        (aarav, "outgoing", "Author sign-off: all 8 claims verified against production code."),
        (meera, "lead", "Lead sign-off: dual sign-off complete. Ready for successor delivery."),
    ]:
        s = session.exec(select(Signoff).where(Signoff.handover_id == h2.id, Signoff.user_id == u.id)).first()
        if not s:
            sig = compute_signoff_hmac(settings.secret_key, h2.id, 1, hv2.hash, u.id, now.isoformat())
            s = Signoff(
                handover_id=h2.id,
                version=1,
                user_id=u.id,
                role=urole,
                signature=sig,
                signed_at=now - timedelta(hours=5),
                comment=comment,
            )
            session.add(s)
    session.flush()

    # -------------------------------------------------------------------------
    # 5. Handover 3: Acquirer Integration & Merchant Sandbox (Status: DELIVERED)
    # -------------------------------------------------------------------------
    h3 = session.exec(
        select(Handover).where(
            Handover.project_id == payflow.id,
            Handover.notes == "Acquirer Integration & Merchant Sandbox",
        )
    ).first()

    if not h3:
        h3 = Handover(
            project_id=payflow.id,
            outgoing_user_id=aarav.id,
            successor_user_id=kabir.id,
            lead_user_id=meera.id,
            status="delivered",
            current_version=1,
            due_date=now - timedelta(days=2),
            notes="Acquirer Integration & Merchant Sandbox",
        )
        session.add(h3)
        session.flush()
    else:
        h3.status = "delivered"
        session.add(h3)
        session.flush()

    # Claims for Handover 3
    h3_claims = [
        (
            "architecture_decision",
            "AcquirerCorp v2 REST API integration completed with mutual TLS authentication.",
            "accepted",
            0.97,
            1,
        ),
        (
            "runbook",
            "Merchant sandbox onboarding: generate test keys via /api/v1/merchants/test-credentials.",
            "accepted",
            0.95,
            1,
        ),
        (
            "blocker",
            "Merchant webhook test suites require mock acquirer callback listener in Docker.",
            "accepted",
            0.92,
            1,
        ),
    ]
    for idx, (kind, text, st, conf, sens) in enumerate(h3_claims):
        cl = session.exec(select(Claim).where(Claim.handover_id == h3.id, Claim.text == text)).first()
        if not cl:
            cl = Claim(
                project_id=payflow.id,
                handover_id=h3.id,
                section="Acquirer Integration",
                kind=kind,
                text=text,
                status=st,
                confidence=conf,
                sensitivity=sens,
                evidence=_evidence("docs/architecture-overview.md", "Mutual TLS Acquirer configuration."),
                origin="llm",
                order_index=idx,
            )
            session.add(cl)
    session.flush()

    # Version 1 Snapshot for Handover 3
    hv3 = session.exec(
        select(HandoverVersion).where(HandoverVersion.handover_id == h3.id, HandoverVersion.version == 1)
    ).first()
    if not hv3:
        snapshot3 = {
            "claims_count": len(h3_claims),
            "handover_notes": h3.notes,
            "status": "delivered",
        }
        hv3_hash = compute_version_hash("", snapshot3)
        hv3 = HandoverVersion(
            handover_id=h3.id,
            version=1,
            snapshot=snapshot3,
            prev_hash="",
            hash=hv3_hash,
            created_by=aarav.id,
            reason="Delivered handover package for Acquirer Integration",
        )
        session.add(hv3)
        session.flush()

    # Both sign-offs for Handover 3
    for u, urole in [(aarav, "outgoing"), (meera, "lead")]:
        s = session.exec(select(Signoff).where(Signoff.handover_id == h3.id, Signoff.user_id == u.id)).first()
        if not s:
            sig = compute_signoff_hmac(settings.secret_key, h3.id, 1, hv3.hash, u.id, now.isoformat())
            session.add(
                Signoff(
                    handover_id=h3.id,
                    version=1,
                    user_id=u.id,
                    role=urole,
                    signature=sig,
                    signed_at=now - timedelta(days=3),
                    comment="Approved for delivery.",
                )
            )
    session.flush()

    # Comprehension Receipts for Successor Kabir
    h3_receipts = [
        (
            "Architecture & Decision History",
            "Understood the rationale behind mutual TLS and Postgres migration.",
        ),
        (
            "Webhook Operations Runbook",
            "Tested the DLQ replay script in local sandbox; procedure is clear and verified.",
        ),
    ]
    for section_name, note in h3_receipts:
        rec = session.exec(
            select(Receipt).where(Receipt.handover_id == h3.id, Receipt.section == section_name)
        ).first()
        if not rec:
            session.add(
                Receipt(
                    handover_id=h3.id,
                    user_id=kabir.id,
                    section=section_name,
                    acknowledged_at=now - timedelta(days=1),
                    comprehension_note=note,
                )
            )
    session.flush()

    # Copilot Chat History for Handover 3
    session_record = session.exec(
        select(ChatSession).where(ChatSession.handover_id == h3.id, ChatSession.user_id == kabir.id)
    ).first()
    if not session_record:
        session_record = ChatSession(handover_id=h3.id, user_id=kabir.id)
        session.add(session_record)
        session.flush()

        # Seed realistic conversation
        q1 = ChatMessage(
            session_id=session_record.id,
            role="user",
            content="Where is the webhook retry policy defined, and what happens when acquirer returns 504?",
        )
        session.add(q1)
        session.flush()

        a1_text = (
            "The webhook retry policy is defined in `backend/app/webhooks/dispatcher.py` (PR #65). "
            "When AcquirerCorp returns 504 Gateway Timeout, an exponential backoff sequence starts "
            "(base delay: 1s, max attempts: 5). If all attempts fail, events park in the DLQ."
        )
        a1 = ChatMessage(
            session_id=session_record.id,
            role="assistant",
            content=a1_text,
            citations=[
                {
                    "artifact_id": art_list[0].id if art_list else "art_doc_runbook",
                    "source_uri": "docs/runbook-webhooks.md",
                    "snippet": "Retry policy: base delay 1s, max attempts 5, then park in DLQ.",
                }
            ],
        )
        session.add(a1)

        q2 = ChatMessage(
            session_id=session_record.id,
            role="user",
            content="Who is the primary vendor escalation contact if sandbox credentials expire?",
        )
        session.add(q2)
        session.flush()

        a2_text = (
            "For vendor escalation, contact David Vance (Head of Integration Engineering at AcquirerCorp) "
            "at `david.vance@acquirercorp.com`, as documented in blocker ticket PAY-142."
        )
        a2 = ChatMessage(
            session_id=session_record.id,
            role="assistant",
            content=a2_text,
            citations=[
                {
                    "artifact_id": art_list[0].id if art_list else "art_jira_142",
                    "source_uri": "jira://PAY-142",
                    "snippet": "Escalation contact: David Vance (david.vance@acquirercorp.com).",
                }
            ],
        )
        session.add(a2)
        session.flush()

    # -------------------------------------------------------------------------
    # 6. Handover 4: Real-Time Fraud Detection (Status: DRAFT)
    # -------------------------------------------------------------------------
    h4 = session.exec(
        select(Handover).where(
            Handover.project_id == payflow.id,
            Handover.notes == "Real-Time Fraud Detection & Risk Pipeline",
        )
    ).first()

    if not h4:
        h4 = Handover(
            project_id=payflow.id,
            outgoing_user_id=aarav.id,
            successor_user_id=kabir.id,
            lead_user_id=meera.id,
            status="draft",
            current_version=1,
            due_date=now + timedelta(days=21),
            notes="Real-Time Fraud Detection & Risk Pipeline",
        )
        session.add(h4)
        session.flush()

    # Draft claims
    h4_claims = [
        (
            "risk",
            "Velocity checks reject >10 transactions/minute from identical IP ranges.",
            "draft",
            0.88,
            1,
        ),
        (
            "architecture_decision",
            "Kafka event stream topic 'transactions.raw' consumed by risk evaluation workers.",
            "draft",
            0.90,
            1,
        ),
        (
            "open_work",
            "Migrate fraud score threshold from static 75 to machine-learning classifier.",
            "draft",
            0.82,
            1,
        ),
    ]
    for idx, (kind, text, st, conf, sens) in enumerate(h4_claims):
        cl = session.exec(select(Claim).where(Claim.handover_id == h4.id, Claim.text == text)).first()
        if not cl:
            session.add(
                Claim(
                    project_id=payflow.id,
                    handover_id=h4.id,
                    section="Risk Pipeline Draft",
                    kind=kind,
                    text=text,
                    status=st,
                    confidence=conf,
                    sensitivity=sens,
                    evidence=_evidence("docs/architecture-overview.md", "Kafka transaction streaming."),
                    origin="llm",
                    order_index=idx,
                )
            )
    session.flush()

    # -------------------------------------------------------------------------
    # 7. Handover 5: CloudMesh Edge Ingress (Project: CloudMesh, Status: IN_REVIEW)
    # Demonstrates contractor role review for Dev Mukherjee
    # -------------------------------------------------------------------------
    h5 = session.exec(
        select(Handover).where(
            Handover.project_id == cloudmesh.id,
            Handover.notes == "Envoy Proxy Edge Routing & TLS Termination",
        )
    ).first()

    if not h5:
        h5 = Handover(
            project_id=cloudmesh.id,
            outgoing_user_id=aarav.id,
            successor_user_id=dev.id,
            lead_user_id=meera.id,
            status="in_review",
            current_version=1,
            due_date=now + timedelta(days=10),
            notes="Envoy Proxy Edge Routing & TLS Termination",
        )
        session.add(h5)
        session.flush()

        session.add(
            Claim(
                project_id=cloudmesh.id,
                handover_id=h5.id,
                section="Gateway Ingress",
                kind="architecture_decision",
                text="Envoy Proxy configured with dynamic mTLS upstream discovery via SPIRE.",
                status="accepted",
                confidence=0.96,
                sensitivity=1,
                evidence=[],
                origin="llm",
                order_index=0,
            )
        )
        session.add(
            Claim(
                project_id=cloudmesh.id,
                handover_id=h5.id,
                section="Gateway Ingress",
                kind="risk",
                text="Edge certificate renewal script requires access to internal Let's Encrypt proxy.",
                status="needs_review",
                confidence=0.91,
                sensitivity=2,
                evidence=[],
                origin="llm",
                order_index=1,
            )
        )
        session.flush()

    # -------------------------------------------------------------------------
    # 8. Handover 6: AuthCore Token Authority (Project: AuthCore, Status: SIGNED)
    # -------------------------------------------------------------------------
    h6 = session.exec(
        select(Handover).where(
            Handover.project_id == authcore.id,
            Handover.notes == "OAuth2 PKCE Session Migration & RBAC Directory",
        )
    ).first()

    if not h6:
        h6 = Handover(
            project_id=authcore.id,
            outgoing_user_id=aarav.id,
            successor_user_id=kabir.id,
            lead_user_id=meera.id,
            status="signed",
            current_version=1,
            due_date=now + timedelta(days=5),
            notes="OAuth2 PKCE Session Migration & RBAC Directory",
        )
        session.add(h6)
        session.flush()

        session.add(
            Claim(
                project_id=authcore.id,
                handover_id=h6.id,
                section="OAuth2 Security",
                kind="architecture_decision",
                text="PKCE code challenge required for all single-page application authorization flows.",
                status="accepted",
                confidence=0.99,
                sensitivity=1,
                evidence=[],
                origin="llm",
                order_index=0,
            )
        )
        session.flush()

    # -------------------------------------------------------------------------
    # 9. Redaction Events & Cryptographic Audit Trail
    # -------------------------------------------------------------------------
    redactions_spec = [
        ("api_key", "[REDACTED:API_KEY]", "slack_leads-private.json"),
        ("aws_key", "[REDACTED:AWS_KEY]", "slack_leads-private.json"),
        ("bearer_token", "[REDACTED:BEARER_TOKEN]", "slack_incidents.json"),
        ("db_url", "[REDACTED:DB_URL]", "slack_leads-private.json"),
        ("email", "[REDACTED:EMAIL]", "slack_leads-private.json"),
        ("phone", "[REDACTED:PHONE]", "slack_leads-private.json"),
        ("salary", "[REDACTED:COMPENSATION]", "slack_leads-private.json"),
    ]

    for rkind, masked, src_name in redactions_spec:
        art = next(
            (a for a in pf_artifacts if src_name in a.source_uri),
            art_list[0] if art_list else None,
        )
        if art:
            existing_re = session.exec(
                select(RedactionEvent).where(
                    RedactionEvent.artifact_id == art.id, RedactionEvent.rule == rkind
                )
            ).first()
            if not existing_re:
                session.add(
                    RedactionEvent(
                        artifact_id=art.id,
                        rule=rkind,
                        count=1,
                        sample_masked=masked,
                    )
                )
    session.flush()

    # Append sequential audit actions to build a rich cryptographic log
    audit_events = [
        (aarav.id, "USER_LOGIN", "user", aarav.id, {"ip": "127.0.0.1", "role": "outgoing"}),
        (meera.id, "USER_LOGIN", "user", meera.id, {"ip": "127.0.0.1", "role": "lead"}),
        (
            meera.id,
            "PROJECT_INITIALIZED",
            "project",
            payflow.id,
            {"name": "PayFlow", "slug": "payflow"},
        ),
        (
            aarav.id,
            "SOURCE_CONNECTED",
            "source",
            "src_github_01",
            {"type": "github", "repo": "payflow/payflow"},
        ),
        (
            aarav.id,
            "SOURCE_CONNECTED",
            "source",
            "src_slack_01",
            {"type": "slack_json", "channels": 3},
        ),
        (
            aarav.id,
            "SECRETS_SCRUBBED",
            "redaction",
            payflow.id,
            {"scrubbed_count": len(redactions_spec)},
        ),
        (
            aarav.id,
            "HANDOVER_CREATED",
            "handover",
            h1.id,
            {"status": "draft", "outgoing": aarav.id, "successor": kabir.id},
        ),
        (
            aarav.id,
            "PIPELINE_RUN",
            "job",
            "job_01",
            {"stage": "extract_and_verify", "claims_extracted": 12},
        ),
        (
            aarav.id,
            "CLAIM_ACCEPTED",
            "claim",
            h1.id,
            {"claim_kind": "architecture_decision", "confidence": 0.96},
        ),
        (
            aarav.id,
            "SIGNOFF_RECORDED",
            "signoff",
            h1.id,
            {"signer_role": "outgoing", "version": 1},
        ),
        (
            meera.id,
            "HANDOVER_CREATED",
            "handover",
            h2.id,
            {"status": "in_review", "outgoing": aarav.id},
        ),
        (
            aarav.id,
            "SIGNOFF_RECORDED",
            "signoff",
            h2.id,
            {"signer_role": "outgoing", "version": 1},
        ),
        (
            meera.id,
            "SIGNOFF_RECORDED",
            "signoff",
            h2.id,
            {"signer_role": "lead", "version": 1},
        ),
        (
            meera.id,
            "HANDOVER_TAMPER_SEALED",
            "handover",
            h2.id,
            {"status": "signed", "version": 1},
        ),
        (
            meera.id,
            "HANDOVER_DELIVERED",
            "handover",
            h3.id,
            {"status": "delivered", "successor": kabir.id},
        ),
        (
            kabir.id,
            "RECEIPT_ACKNOWLEDGED",
            "receipt",
            h3.id,
            {"section": "Architecture & Decision History"},
        ),
        (
            kabir.id,
            "RECEIPT_ACKNOWLEDGED",
            "receipt",
            h3.id,
            {"section": "Webhook Operations Runbook"},
        ),
        (
            sana.id,
            "AUDIT_CHAIN_VERIFIED",
            "governance",
            payflow.id,
            {"result": "VERIFIED_VALID", "entries_inspected": 25},
        ),
    ]

    for actor, action, t_type, t_id, payload in audit_events:
        audit(
            session,
            actor_id=actor,
            action=action,
            target_type=t_type,
            target_id=t_id,
            payload=payload,
        )

    session.commit()
    logger.info("Demo data seeding completed successfully across all modes.")
    return {
        "status": "ok",
        "projects_count": len(projects),
        "users_count": len(users),
        "handovers_seeded": [h1.id, h2.id, h3.id, h4.id, h5.id, h6.id],
    }
