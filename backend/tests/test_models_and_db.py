"""Tests for P02: Database models, migrations, FTS5 sync, and audit chain verification."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db import audit, search_artifacts, utcnow, verify_audit_chain
from app.models import (
    Artifact,
    Project,
    SchemaVersion,
    Source,
)


def test_schema_creation_and_migrations(session: Session) -> None:
    """Verify that all expected tables are created and migration 0001 is recorded."""
    engine = session.get_bind()
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "user",
        "project",
        "project_member",
        "source",
        "artifact",
        "redaction_event",
        "entity",
        "node",
        "edge",
        "handover",
        "claim",
        "ambiguity",
        "handover_version",
        "signoff",
        "plan_item",
        "receipt",
        "chat_session",
        "chat_message",
        "job",
        "audit_log",
        "schema_version",
        "artifact_fts",
    }
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"

    # Verify migration 0001 recorded
    migrations = session.exec(select(SchemaVersion).order_by(SchemaVersion.version.asc())).all()
    assert len(migrations) >= 1
    assert migrations[0].version == 1
    assert "fts" in migrations[0].description.lower()


def test_unique_artifact_idempotency(session: Session) -> None:
    """UNIQUE(project_id, kind, external_id) ensures idempotent ingestion and prevents duplicates."""
    proj = Project(name="PayFlow", slug="payflow")
    src = Source(project_id=proj.id, type="github", name="PayFlow Repo")
    session.add_all([proj, src])
    session.commit()

    art1 = Artifact(
        project_id=proj.id,
        source_id=src.id,
        kind="commit",
        external_id="c101",
        source_uri="https://github.com/payflow/commit/c101",
        title="Refactor webhooks",
        body_redacted="Refactored webhook dispatcher",
        body_hash="hash1",
        author_alias="aarav",
        valid_time=utcnow(),
        sensitivity=1,
    )
    session.add(art1)
    session.commit()

    # Second artifact with identical (project_id, kind, external_id)
    art2 = Artifact(
        project_id=proj.id,
        source_id=src.id,
        kind="commit",
        external_id="c101",
        source_uri="https://github.com/payflow/commit/c101_dup",
        title="Refactor webhooks duplicate",
        body_redacted="Duplicate commit",
        body_hash="hash2",
        author_alias="aarav",
        valid_time=utcnow(),
        sensitivity=1,
    )
    session.add(art2)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_fts_sync_and_sensitivity_permission_filter(session: Session) -> None:
    """Artifacts sync to FTS5, and search_artifacts enforces SQL sensitivity firewall."""
    proj = Project(name="PayFlow", slug="payflow-fts")
    src = Source(project_id=proj.id, type="github", name="PayFlow Repo")
    session.add_all([proj, src])
    session.commit()

    # Artifact with sensitivity 1 (Internal)
    art_internal = Artifact(
        project_id=proj.id,
        source_id=src.id,
        kind="pull_request",
        external_id="pr_89",
        source_uri="https://github.com/payflow/pull/89",
        title="Switch to stateless JWT tokens",
        body_redacted="Replaced Redis session store with stateless HMAC-signed JWT tokens.",
        body_hash="h89",
        author_alias="aarav",
        valid_time=utcnow(),
        sensitivity=1,
    )

    # Artifact with sensitivity 2 (Confidential)
    art_confidential = Artifact(
        project_id=proj.id,
        source_id=src.id,
        kind="chat_thread",
        external_id="slack_leads_12",
        source_uri="https://payflow.slack.com/archives/leads/12",
        title="Vendor escalation and contractor compensation",
        body_redacted="Vendor contract terms and payment rate limits for stateless JWT integrations.",
        body_hash="h12",
        author_alias="meera",
        valid_time=utcnow(),
        sensitivity=2,
    )

    session.add_all([art_internal, art_confidential])
    session.commit()

    # 1. Search with clearance 1: only internal artifact returned, confidential is filtered in SQL
    results_cleared_1 = search_artifacts(
        session,
        project_id=proj.id,
        query="stateless JWT",
        max_sensitivity=1,
    )
    assert len(results_cleared_1) == 1
    assert results_cleared_1[0].id == art_internal.id

    # 2. Search with clearance 2: both returned
    results_cleared_2 = search_artifacts(
        session,
        project_id=proj.id,
        query="stateless JWT",
        max_sensitivity=2,
    )
    assert len(results_cleared_2) == 2
    returned_ids = {a.id for a in results_cleared_2}
    assert returned_ids == {art_internal.id, art_confidential.id}

    # 3. Test FTS trigger sync on UPDATE
    art_internal.body_redacted = "Updated body mentioning microservice architecture."
    session.add(art_internal)
    session.commit()

    results_updated = search_artifacts(
        session,
        project_id=proj.id,
        query="microservice",
        max_sensitivity=1,
    )
    assert len(results_updated) == 1
    assert results_updated[0].id == art_internal.id

    # 4. Test FTS trigger sync on DELETE
    session.delete(art_internal)
    session.commit()

    results_deleted = search_artifacts(
        session,
        project_id=proj.id,
        query="microservice",
        max_sensitivity=1,
    )
    assert len(results_deleted) == 0


def test_audit_chain_tamper_detection(session: Session) -> None:
    """Audit records form a hash chain; tampering causes verify_audit_chain to return False."""
    assert verify_audit_chain(session) is True

    # Insert 3 chained audit logs
    e1 = audit(
        session,
        actor_id="user_1",
        action="CREATE_PROJECT",
        target_type="project",
        target_id="p1",
        payload={"name": "P1"},
    )
    session.commit()

    e2 = audit(
        session,
        actor_id="user_1",
        action="INGEST_ARTIFACT",
        target_type="artifact",
        target_id="a1",
        payload={"count": 10},
    )
    session.commit()

    e3 = audit(
        session,
        actor_id="user_2",
        action="EDIT_CLAIM",
        target_type="claim",
        target_id="c1",
        payload={"diff": "+1 -1"},
    )
    session.commit()

    # Chain must be valid
    assert verify_audit_chain(session) is True
    assert e1.prev_hash == ""
    assert e2.prev_hash == e1.hash
    assert e3.prev_hash == e2.hash

    # Tamper with record 2 directly in DB
    session.execute(
        text("UPDATE audit_log SET action = 'MALICIOUS_TAMPER' WHERE seq = :seq"),
        {"seq": e2.seq},
    )
    session.commit()

    # The chain verification must fail!
    assert verify_audit_chain(session) is False
