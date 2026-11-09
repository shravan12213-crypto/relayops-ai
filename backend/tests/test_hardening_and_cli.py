"""Tests for backend hardening, security headers, route authorization, 50 parallel requests, and CLI.

Enforces acceptance criteria for P13:
- Authorization check on EVERY route through a dependency (except /health and /auth/login).
- DB session concurrency test with 50 parallel requests (no leaks, no lockouts).
- Security headers middleware (X-Content-Type-Options, X-Frame-Options,
  Referrer-Policy, strict CSP, X-Request-ID).
- OpenAPI docs availability strictly gated by ENV=dev.
- CLI commands: seed, reset-db, record-llm, verify-chain, create-user.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import create_access_token, get_current_user
from app.cli import main as cli_main
from app.config import get_settings
from app.main import app, create_app
from app.models import Project, User
from app.routers.sources import execute_demo_load

# ---------------------------------------------------------------------------
# 1. Route Authorization Audit Test
# ---------------------------------------------------------------------------


def test_all_routes_require_authorization() -> None:
    """Enumerate all routes in the application and verify that every route has an auth dependency

    except /api/v1/health and /api/v1/auth/login.
    """
    allowed_unauthenticated_paths = {
        "/api/v1/health",
        "/auth/login",
        "/api/v1/auth/login",
    }

    all_routes: list[Any] = []
    for r in app.routes:
        if type(r).__name__ == "_IncludedRouter":
            all_routes.extend(r.original_router.routes)
        elif hasattr(r, "endpoint"):
            all_routes.append(r)

    unprotected_routes: list[str] = []

    for route in all_routes:
        path = getattr(route, "path", "")
        # Skip static SPA index fallback route or docs
        if path in ("", "/", "/api/docs", "/api/openapi.json", "/docs/oauth2-redirect"):
            continue

        if path in allowed_unauthenticated_paths:
            continue

        # Check if get_current_user is present in the route's dependencies
        dependant = getattr(route, "dependant", None)
        if not dependant:
            continue

        has_auth = any(d.call == get_current_user for d in dependant.dependencies)
        if not has_auth:
            unprotected_routes.append(f"{list(route.methods)[0]} {path}")

    assert (
        not unprotected_routes
    ), f"Security check failed! The following routes lack an authentication dependency: {unprotected_routes}"


def test_unauthenticated_access_is_rejected(client: TestClient) -> None:
    """Unauthenticated requests to protected endpoints receive 401 UNAUTHENTICATED."""
    # Attempt to fetch users without auth
    res = client.get("/api/v1/users")
    assert res.status_code == 401
    err = res.json()["error"]
    assert err["code"] == "UNAUTHENTICATED"
    assert "request_id" in err["details"]

    # Attempt to fetch me without auth
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 401

    # Attempt to logout without auth
    logout_res = client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 401


# ---------------------------------------------------------------------------
# 2. Concurrency & DB Session Leak Test (50 Parallel Requests)
# ---------------------------------------------------------------------------


def test_50_parallel_requests_no_db_leak(client: TestClient, session: Session) -> None:
    """Execute 50 parallel requests simultaneously against the API.

    Verifies WAL mode concurrency, absence of connection pool starvation or session leaks.
    """
    execute_demo_load(session)
    user = session.exec(select(User).where(User.email == "aarav@payflow.dev")).one()
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    def fire_request(req_idx: int) -> int:
        if req_idx % 2 == 0:
            res = client.get("/api/v1/health")
        else:
            res = client.get("/api/v1/auth/me", headers=headers)
        return res.status_code

    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(fire_request, i) for i in range(50)]
        results = [f.result() for f in futures]

    assert len(results) == 50
    assert all(code == 200 for code in results), f"Some parallel requests failed: {set(results)}"

    # Verify database session is fully responsive immediately after
    refreshed_user = session.exec(select(User).where(User.email == "aarav@payflow.dev")).first()
    assert refreshed_user is not None


# ---------------------------------------------------------------------------
# 3. Security Headers Middleware Test
# ---------------------------------------------------------------------------


def test_security_headers_middleware(client: TestClient) -> None:
    """Verify security headers and request-ID are included in all HTTP responses."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200

    headers = res.headers
    assert "x-request-id" in headers or "X-Request-ID" in headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]


# ---------------------------------------------------------------------------
# 4. OpenAPI Documentation Environment Gating Test
# ---------------------------------------------------------------------------


def test_openapi_docs_env_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Docs are available at /api/docs only when ENV=dev."""
    # 1. In dev mode -> 200 OK
    monkeypatch.setenv("ENV", "dev")
    get_settings.cache_clear()
    app_dev = create_app()
    client_dev = TestClient(app_dev)
    docs_res = client_dev.get("/api/docs")
    assert docs_res.status_code == 200
    openapi_res = client_dev.get("/api/openapi.json")
    assert openapi_res.status_code == 200

    # 2. In prod mode -> 404 Not Found
    monkeypatch.setenv("ENV", "prod")
    get_settings.cache_clear()
    app_prod = create_app()
    client_prod = TestClient(app_prod)
    docs_prod = client_prod.get("/api/docs")
    assert docs_prod.status_code == 404
    openapi_prod = client_prod.get("/api/openapi.json")
    assert openapi_prod.status_code == 404

    # Reset cache
    monkeypatch.undo()
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# 5. CLI Maintenance Commands Test
# ---------------------------------------------------------------------------


def test_cli_commands(session: Session) -> None:
    """Verify all 5 CLI commands execute successfully:

    seed, verify-chain, create-user, record-llm, reset-db.
    """
    # 1. Test create-user CLI command
    rc_user = cli_main(
        [
            "create-user",
            "--email",
            "cli_test_user@payflow.dev",
            "--name",
            "CLI Tester",
            "--password",
            "SuperSecretPassword123!",
            "--role",
            "contractor",
            "--clearance",
            "1",
        ]
    )
    assert rc_user == 0
    created = session.exec(select(User).where(User.email == "cli_test_user@payflow.dev")).first()
    assert created is not None
    assert created.role == "contractor"
    assert created.clearance == 1

    # 2. Test verify-chain CLI command
    rc_verify = cli_main(["verify-chain"])
    assert rc_verify == 0

    # 3. Test record-llm CLI command
    rc_record = cli_main(["record-llm"])
    assert rc_record == 0

    # 4. Test seed CLI command
    rc_seed = cli_main(["seed"])
    assert rc_seed == 0

    # 5. Test reset-db CLI command
    rc_reset = cli_main(["reset-db"])
    assert rc_reset == 0


# ---------------------------------------------------------------------------
# 6. Standardized Pagination Test
# ---------------------------------------------------------------------------


def test_standardized_pagination(client: TestClient, session: Session) -> None:
    """Standardized pagination returns {items, total, page, page_size}."""
    execute_demo_load(session)
    user = session.exec(select(User).where(User.email == "aarav@payflow.dev")).one()
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    # Find project
    proj = session.exec(select(Project).where(Project.slug == "payflow")).first()
    assert proj is not None

    # Create a handover to query claims
    h_res = client.post(
        f"/api/v1/projects/{proj.id}/handovers",
        json={
            "outgoing_user_id": user.id,
            "successor_user_id": user.id,
            "lead_user_id": user.id,
            "notes": "Pagination test handover",
        },
        headers=headers,
    )
    assert h_res.status_code == 201
    handover_id = h_res.json()["id"]

    # Query claims with standardized page & page_size and paged=True
    claims_res = client.get(
        f"/api/v1/handovers/{handover_id}/claims?page=1&page_size=10&paged=true",
        headers=headers,
    )
    assert claims_res.status_code == 200
    data = claims_res.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert claims_res.headers.get("X-Page") == "1"
    assert claims_res.headers.get("X-Page-Size") == "10"


def test_cli_backup_command(tmp_path: Any) -> None:
    """Verify `python -m app.cli backup` safely backs up SQLite database using online backup API."""
    import sqlite3

    dest_backup = tmp_path / "relayops_backup_test.db"
    code = cli_main(["backup", "--dest", str(dest_backup)])
    assert code == 0
    assert dest_backup.exists()
    assert dest_backup.stat().st_size > 0

    # Verify backup is a valid sqlite database
    conn = sqlite3.connect(dest_backup)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    assert "user" in tables or "project" in tables


def test_check_prod_safety_fails_on_default_or_weak_secret_key() -> None:
    """Verify check_prod_safety fails fast with a clear error message in production
    when SECRET_KEY is default or weak.
    """
    from app.config import DEFAULT_SECRET_KEY, Settings

    # Default secret key in prod must fail
    prod_bad = Settings(env="prod", secret_key=DEFAULT_SECRET_KEY)
    with pytest.raises(RuntimeError, match="Unsafe production configuration detected"):
        prod_bad.check_prod_safety()

    # Short secret key in prod must fail
    prod_short = Settings(env="prod", secret_key="short-secret-key")
    with pytest.raises(RuntimeError, match="Unsafe production configuration detected"):
        prod_short.check_prod_safety()

    # ENV=production alias must also be normalized and fail on bad key
    prod_alias_bad = Settings(env="production", secret_key=DEFAULT_SECRET_KEY)
    with pytest.raises(RuntimeError, match="Unsafe production configuration detected"):
        prod_alias_bad.check_prod_safety()

    # Strong key in prod must pass
    prod_good = Settings(env="prod", secret_key="a" * 48)
    prod_good.check_prod_safety()
