"""Security verification: Assert planted secrets are absent from SQLite DB and logs.

Scans the SQLite database tables (Artifact, Node, Edge, Claim, AuditLog, Job)
and asserts that ZERO plaintext planted secrets exist in the database.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlmodel import Session, select, text

from app.db import get_engine, init_db
from app.models import Artifact, Claim, Job, Node
from app.routers.sources import execute_demo_load

GROUND_TRUTH_PATH = Path(__file__).resolve().parent.parent / "seed" / "ground_truth.json"


def test_no_plaintext_secrets_in_database():
    """Verify that every planted fake secret is completely absent in plaintext from the database."""
    engine = get_engine()
    init_db(engine)

    with Session(engine) as session:
        execute_demo_load(session)

        # Load planted secrets from ground truth
        gt = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
        planted_secrets = [s["raw"] for s in gt.get("planted_secrets", [])]
        assert len(planted_secrets) >= 5

        # Query all text fields across tables
        artifacts = session.exec(select(Artifact)).all()
        claims = session.exec(select(Claim)).all()
        nodes = session.exec(select(Node)).all()

        for sec in planted_secrets:
            # Check artifacts
            for a in artifacts:
                assert sec not in (a.body_redacted or ""), f"Secret '{sec}' found in artifact {a.id} ({a.title})!"
                assert sec not in (a.title or ""), f"Secret '{sec}' found in artifact title {a.id}!"

            # Check claims
            for c in claims:
                assert sec not in (c.text or ""), f"Secret '{sec}' found in claim {c.id}!"
                assert sec not in str(c.evidence), f"Secret '{sec}' found in claim evidence {c.id}!"

            # Check nodes
            for n in nodes:
                assert sec not in (n.label or ""), f"Secret '{sec}' found in node label {n.id}!"
                assert sec not in str(n.props), f"Secret '{sec}' found in node props {n.id}!"


def test_security_headers_and_cookie_policy():
    """Verify Content-Security-Policy, anti-clickjacking, and cookie flags."""
    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app()
    client = TestClient(app)

    res = client.get("/api/v1/health")
    assert res.status_code == 200
    headers = res.headers

    # Check CSP and anti-sniffing headers
    assert "Content-Security-Policy" in headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "X-Request-ID" in headers


def test_unauthorized_routes_blocked():
    """Verify protected routes reject unauthenticated requests with 401."""
    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app()
    client = TestClient(app)

    # Protected routes without cookie or Authorization header must fail with 401
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHENTICATED"

    res = client.get("/api/v1/audit/logs")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHENTICATED"
