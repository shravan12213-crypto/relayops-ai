"""End-to-end multi-run verification test for RelayOps demo script (docs/DEMO_SCRIPT.md).

Executes the complete demo walkthrough 3 consecutive times from a clean reset database:
1. Reset database + load PayFlow seed demo (sources, users, redacted artifacts)
2. Run pipeline (graph reconstruction, claim extraction, conflict/ambiguity detection, scorecard)
3. Review Studio operations (citation binding, claim edit, ambiguity resolution, snapshot v1)
4. Dual sign-off (Aarav outgoing sign, Meera lead sign) -> deliver handover
5. Successor Portal (reading receipt acknowledgement, Day 1-30 board task transition)
6. Grounded Copilot (answering PAY-142 with citations, deterministic refusal on missing evidence)
7. Multi-Role ABAC firewall (Contractor Dev masked confidential items)
8. Cryptographic audit chain verification (Auditor Sana)

Measures execution duration per run and confirms zero flakiness.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest
from sqlmodel import SQLModel, Session, select

from app.db import get_engine, init_db, verify_audit_chain_detailed
from app.errors import AppError
from app.handover.claims import AmbiguityResolveInput, patch_claim, resolve_ambiguity
from app.handover.copilot import DETERMINISTIC_REFUSAL_PREFIX, ask_copilot
from app.handover.receipts import ReceiptInput, acknowledge_section_receipt
from app.handover.signoff import execute_signoff
from app.handover.versions import create_snapshot
from app.handover.views import build_handover_view, deliver_handover
from app.jobs import run_handover_pipeline
from app.models import (
    Ambiguity,
    Claim,
    Handover,
    Job,
    PlanItem,
    Project,
    User,
)
from app.routers.sources import execute_demo_load


def execute_full_demo_cycle(cycle_num: int) -> dict[str, float | int | bool]:
    """Execute the full demo script lifecycle from a clean reset database."""
    engine = get_engine()
    start_time = time.perf_counter()

    # Step 1: Clean reset database
    SQLModel.metadata.drop_all(engine)
    init_db(engine)

    with Session(engine) as session:
        # Step 2: Ingest PayFlow demo sources and scrubbed artifacts
        project, counts, total_artifacts = execute_demo_load(session)
        assert project is not None
        assert total_artifacts > 50

        # Fetch users
        aarav = session.exec(select(User).where(User.email == "aarav@payflow.dev")).one()
        meera = session.exec(select(User).where(User.email == "meera@payflow.dev")).one()
        kabir = session.exec(select(User).where(User.email == "kabir@payflow.dev")).one()
        dev = session.exec(select(User).where(User.email == "dev@payflow.dev")).one()
        sana = session.exec(select(User).where(User.email == "sana@payflow.dev")).one()

        assert aarav.role == "outgoing"
        assert meera.role == "lead"
        assert kabir.role == "successor"
        assert dev.role == "contractor"
        assert sana.role == "auditor"

        # Step 3: Run pipeline (Connect -> Reconstruct -> Verify)
        handover = Handover(
            project_id=project.id,
            outgoing_user_id=aarav.id,
            successor_user_id=kabir.id,
            lead_user_id=meera.id,
            due_date=datetime(2026, 11, 30, tzinfo=UTC),
            status="reconstructing",
            notes=f"PayFlow Demo Run #{cycle_num}",
        )
        session.add(handover)
        session.commit()
        session.refresh(handover)

        # Step 3: Run full 5-stage background pipeline
        job = Job(
            project_id=project.id,
            handover_id=handover.id,
            kind="handover_pipeline",
            status="queued",
            stage="connect_check",
            progress=0,
            log=[],
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        run_handover_pipeline(job.id, handover.id, project.id)

        session.refresh(job)
        assert job.status == "done"
        session.refresh(handover)
        assert handover.status == "in_review"

        # Verify extracted claims and evidence invariants
        claims = session.exec(select(Claim).where(Claim.handover_id == handover.id)).all()
        assert len(claims) > 0
        for c in claims:
            if c.status == "accepted":
                assert len(c.evidence) >= 1

        # Verify ambiguities were flagged
        ambiguities = session.exec(select(Ambiguity).where(Ambiguity.handover_id == handover.id)).all()
        assert len(ambiguities) > 0

        # Step 4: Review Studio operations
        # 4a. Edit a claim with word diff
        target_claim = session.exec(
            select(Claim).where(Claim.handover_id == handover.id, Claim.status == "accepted")
        ).first()
        assert target_claim is not None
        original_text = target_claim.text
        patched = patch_claim(
            session,
            target_claim.id,
            aarav,
            patch_data := type("ClaimPatchInput", (), {
                "text": original_text + " Note: requires rotating webhook secret.",
                "status": "edited",
                "rejected_reason": None,
                "order_index": None,
                "expected_updated_at": None,
            })(),
        )
        assert patched["status"] == "edited"

        # 4b. Demonstrate sign-off blocking guard: blocked while high ambiguities open
        with pytest.raises(AppError) as exc_info:
            execute_signoff(session, handover.id, aarav, version=handover.current_version)
        assert exc_info.value.code == "PRECONDITION_FAILED"
        assert "open HIGH-severity ambiguities remain" in exc_info.value.message

        # 4c. Resolve / waive all high-severity ambiguities
        high_ambs = session.exec(
            select(Ambiguity).where(
                Ambiguity.handover_id == handover.id,
                Ambiguity.severity == "high",
                Ambiguity.status == "open",
            )
        ).all()
        for amb in high_ambs:
            resolve_ambiguity(
                session,
                amb.id,
                aarav,
                AmbiguityResolveInput(resolution_note=f"Resolved during review walkthrough: {amb.title}"),
            )

        # 4d. Ensure all draft claims are accepted/reviewed
        draft_claims = session.exec(
            select(Claim).where(Claim.handover_id == handover.id, Claim.status == "draft")
        ).all()
        for c in draft_claims:
            c.status = "accepted"
            session.add(c)
        session.commit()

        # 4e. Create Snapshot after human review/edits
        snapshot = create_snapshot(session, handover.id, actor_id=aarav.id, reason="Demo Snapshot Final")
        assert snapshot.version >= 1
        assert len(snapshot.hash) == 64  # SHA-256

        # 4f. Dual Sign-Off (Outgoing Aarav + Lead Meera) on the new snapshot
        res_aarav = execute_signoff(session, handover.id, aarav, version=snapshot.version, comment="Aarav reviewed")
        assert res_aarav["both_signed"] is False
        session.refresh(handover)
        assert handover.status == "in_review"

        res_meera = execute_signoff(session, handover.id, meera, version=snapshot.version, comment="Meera approved")
        assert res_meera["both_signed"] is True
        session.refresh(handover)
        assert handover.status == "signed"
        session.refresh(handover)
        assert handover.status == "signed"

        # 4e. Deliver Handover
        deliv = deliver_handover(session, handover.id, meera)
        assert deliv["status"] == "delivered"

        # Step 5: Successor Portal operations (Kabir)
        # 5a. Acknowledge reading receipt
        receipt = acknowledge_section_receipt(
            session,
            handover.id,
            kabir,
            ReceiptInput(
                section="Architecture",
                comprehension_note="Reviewed JWT and DB migrations",
            ),
        )
        assert receipt["section"] == "architecture"

        # 5b. Update Day 1-30 task
        plan_item = PlanItem(
            handover_id=handover.id,
            day_bucket="d1_7",
            title="Setup local PayFlow dev environment",
            description="Clone repo and run migrations",
            priority="high",
            status="todo",
            assignee=kabir.name,
        )
        session.add(plan_item)
        session.commit()
        session.refresh(plan_item)

        plan_item.status = "doing"
        session.add(plan_item)
        session.commit()

        # Step 6: Grounded Copilot (Answer with citations & Refusal)
        # 6a. Answer grounded question (PAY-142)
        copilot_res = ask_copilot(session, handover.id, kabir, "What is blocking vendor sandbox access in PAY-142?")
        assert copilot_res["can_answer"] is True
        assert len(copilot_res["citations"]) >= 1

        # 6b. Deterministic refusal on missing evidence
        refusal_res = ask_copilot(session, handover.id, kabir, "How do we configure the Kubernetes Istio mesh?")
        assert refusal_res["refused"] is True
        assert DETERMINISTIC_REFUSAL_PREFIX in refusal_res["answer"]

        # Step 7: Multi-Role ABAC Firewall (Contractor Dev)
        contractor_view = build_handover_view(session, handover.id, dev)
        assert contractor_view["viewing_role"] == "contractor"
        assert contractor_view["effective_clearance"] <= 1
        # Verify confidential claims are masked
        masked_claims = [c for c in contractor_view["claims"] if c.get("is_masked") is True]
        assert len(masked_claims) >= 1
        for mc in masked_claims:
            assert "Restricted:" in mc["text"]
            assert mc["evidence"] == []

        # Step 8: Cryptographic Audit Chain (Auditor Sana)
        chain_res = verify_audit_chain_detailed(session)
        assert chain_res["valid"] is True
        assert chain_res["entries_count"] > 10

    duration = time.perf_counter() - start_time
    return {
        "cycle": cycle_num,
        "duration_seconds": round(duration, 2),
        "artifacts_ingested": total_artifacts,
        "handover_status": "delivered",
        "audit_chain_valid": True,
    }


def test_demo_script_three_consecutive_runs():
    """Run the complete demo script 3 times consecutively from a reset DB, timing each run."""
    timings: list[float] = []

    for i in range(1, 4):
        result = execute_full_demo_cycle(cycle_num=i)
        duration = float(result["duration_seconds"])
        timings.append(duration)
        print(f"\n[DEMO RUN #{i}] Duration: {duration:.2f}s | Status: {result['handover_status']} | Audit Chain: {result['audit_chain_valid']}")

        # Assert each run completes well under 6 minutes (360s)
        assert duration <= 360.0, f"Demo run #{i} took {duration}s, exceeding 360s limit!"
        assert result["handover_status"] == "delivered"
        assert result["audit_chain_valid"] is True

    avg_duration = sum(timings) / len(timings)
    print(f"\n[SUMMARY] 3/3 Demo runs passed without flakiness! Avg time: {avg_duration:.2f}s (Target <= 360s)")
    assert avg_duration <= 360.0
