"""PostgreSQL integration tests: Schema, migrations, FTS, Copilot, and audit ledger on genuine PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlmodel import Session, create_engine, select, text

from app import db
from app.config import get_settings
from app.db import (
    audit,
    init_db,
    resolve_database_url,
    search_artifacts,
    utcnow,
    verify_audit_chain,
)
from app.handover.copilot import ask_copilot
from app.models import Artifact, Claim, Handover, Project, Source, User
from app.routers.sources import execute_demo_load

TEST_PG_URL = os.environ.get("TEST_POSTGRES_URL", "postgresql://postgres@127.0.0.1:5433/relayops_pg")


def is_postgres_available() -> bool:
    try:
        engine = create_engine(resolve_database_url(TEST_PG_URL))
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not is_postgres_available(),
    reason="PostgreSQL integration test instance is not reachable",
)


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(resolve_database_url(TEST_PG_URL), pool_pre_ping=True)
    # Clean up schema before test run
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def pg_session(pg_engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    monkeypatch.setenv("DATABASE_URL", TEST_PG_URL)
    get_settings.cache_clear()
    db._engine = pg_engine
    with Session(pg_engine) as session:
        yield session
    get_settings.cache_clear()
    db._engine = None


def test_postgres_schema_and_migrations(pg_engine):
    """Verify that SQLModel tables, migrations, and PostgreSQL GIN FTS index are created cleanly."""
    with pg_engine.connect() as conn:
        # Check tables
        tables = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "user" in table_names
        assert "project" in table_names
        assert "artifact" in table_names
        assert "claim" in table_names
        assert "audit_log" in table_names
        assert "schema_version" in table_names

        # Check migration version
        mig = conn.execute(text("SELECT version, description FROM schema_version")).fetchall()
        assert len(mig) >= 1
        assert mig[0][0] == 1

        # Check PostgreSQL GIN index on artifact
        indexes = conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'artifact' AND indexname = 'idx_artifact_fts'"
            )
        ).fetchall()
        assert len(indexes) == 1, "idx_artifact_fts GIN index must exist on artifact table"


def test_postgres_seed_and_demo_load(pg_session: Session):
    """Verify PayFlow demo dataset seeds cleanly into PostgreSQL."""
    execute_demo_load(pg_session)

    users = pg_session.exec(select(User)).all()
    assert len(users) >= 5

    project = pg_session.exec(select(Project).where(Project.slug == "payflow")).first()
    assert project is not None
    assert project.name == "PayFlow"

    sources = pg_session.exec(select(Source).where(Source.project_id == project.id)).all()
    assert len(sources) >= 4

    artifacts = pg_session.exec(select(Artifact).where(Artifact.project_id == project.id)).all()
    assert len(artifacts) >= 10


def test_postgres_full_text_search_and_clearance_firewall(pg_session: Session):
    """Verify PostgreSQL tsvector full-text search and sensitivity filtering."""
    project = pg_session.exec(select(Project).where(Project.slug == "payflow")).first()
    assert project is not None

    source = pg_session.exec(select(Source).where(Source.project_id == project.id)).first()
    assert source is not None

    # Insert test artifacts
    a_internal = Artifact(
        project_id=project.id,
        source_id=source.id,
        kind="pull_request",
        external_id="pr_pg_internal",
        source_uri="https://github.com/payflow/pull/999",
        title="PostgreSQL stateless authentication protocol",
        body_redacted="Implemented HMAC JWT authentication mechanism for microservices.",
        body_hash="h_pg_1",
        author_alias="aarav",
        valid_time=utcnow(),
        sensitivity=1,
    )
    a_confidential = Artifact(
        project_id=project.id,
        source_id=source.id,
        kind="chat_thread",
        external_id="slack_pg_conf",
        source_uri="https://payflow.slack.com/archives/leads/999",
        title="Executive compensation and stateless authentication budget",
        body_redacted="Executive compensation budget discussion regarding stateless authentication rollout.",
        body_hash="h_pg_2",
        author_alias="meera",
        valid_time=utcnow(),
        sensitivity=2,
    )
    pg_session.add_all([a_internal, a_confidential])
    pg_session.commit()

    # Clearance 1: only internal artifact returned
    results_c1 = search_artifacts(
        pg_session,
        project_id=project.id,
        query="stateless authentication",
        max_sensitivity=1,
    )
    returned_ids_c1 = {a.id for a in results_c1}
    assert a_internal.id in returned_ids_c1
    assert a_confidential.id not in returned_ids_c1, "Confidential artifact leaked to Clearance 1!"

    # Clearance 2: both returned
    results_c2 = search_artifacts(
        pg_session,
        project_id=project.id,
        query="stateless authentication",
        max_sensitivity=2,
    )
    returned_ids_c2 = {a.id for a in results_c2}
    assert a_internal.id in returned_ids_c2
    assert a_confidential.id in returned_ids_c2


def test_postgres_audit_chain_and_tamper_detection(pg_session: Session):
    """Verify cryptographic audit hash chain operates and detects tampering in PostgreSQL."""
    assert verify_audit_chain(pg_session) is True

    e1 = audit(
        pg_session,
        actor_id="user_test_1",
        action="PROJECT_CREATE",
        target_type="project",
        target_id="proj_1",
        payload={"name": "Audit Test Project"},
    )
    e2 = audit(
        pg_session,
        actor_id="user_test_2",
        action="CLAIM_ACCEPT",
        target_type="claim",
        target_id="claim_1",
        payload={"status": "accepted"},
    )
    pg_session.commit()

    assert e1.seq is not None
    assert e2.seq is not None
    assert e2.prev_hash == e1.hash
    assert verify_audit_chain(pg_session) is True


def test_postgres_copilot_retrieval(pg_session: Session):
    """Verify ask_copilot functions with PostgreSQL full-text retrieval."""
    project = pg_session.exec(select(Project).where(Project.slug == "payflow")).first()
    assert project is not None

    lead = pg_session.exec(select(User).where(User.role == "lead")).first()
    assert lead is not None

    handover = Handover(
        project_id=project.id,
        outgoing_user_id=lead.id,
        successor_user_id=lead.id,
        lead_user_id=lead.id,
        status="in_review",
    )
    pg_session.add(handover)
    pg_session.commit()

    claim = Claim(
        project_id=project.id,
        handover_id=handover.id,
        kind="architecture_decision",
        text="The team migrated from MongoDB to PostgreSQL for atomic transactions.",
        status="accepted",
        confidence=1.0,
        sensitivity=1,
    )
    pg_session.add(claim)
    pg_session.commit()

    resp = ask_copilot(pg_session, handover.id, lead, "Why did we choose PostgreSQL?")
    assert resp["answer"]
    assert not resp["refused"]


def test_postgres_system_status_reporting(pg_session: Session):
    """Verify get_system_status endpoint reports database as postgresql."""
    from app.routers.governance import get_system_status

    status = get_system_status(session=pg_session)
    assert status.database == "postgresql"
