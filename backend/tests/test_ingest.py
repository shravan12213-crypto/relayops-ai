"""Tests for P05: Ingestion gateway, loaders, normalizer, sources API, and demo dataset loader."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import COOKIE_NAME, create_access_token, hash_password
from app.db import get_engine
from app.ingest.base import RawEvent
from app.ingest.json_loaders import (
    BranchesLoader,
    CommitsLoader,
    IssuesLoader,
    PullRequestsLoader,
    SlackLoader,
)
from app.ingest.markdown import MarkdownLoader
from app.ingest.normalize import compute_authority, compute_sensitivity, normalize_and_upsert_event
from app.models import Artifact, Project, Source, User

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
DATA_DIR = SEED_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"


def get_auth_headers(client: TestClient) -> dict[str, str]:
    with Session(get_engine()) as session:
        user = session.exec(select(User).where(User.email == "testadmin@payflow.dev")).first()
        if not user:
            user = User(
                email="testadmin@payflow.dev",
                name="Test Admin",
                password_hash=hash_password("adminpass123"),
                role="lead",
                clearance=3,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        token = create_access_token(user)
        client.cookies.set(COOKIE_NAME, token)
        return {"Authorization": f"Bearer {token}"}


def test_loaders_on_seed_data_produce_expected_counts() -> None:
    # 1. Commits
    commits_data = json.loads((DATA_DIR / "commits.json").read_text(encoding="utf-8"))
    commit_events = list(CommitsLoader().load(commits_data))
    assert len(commit_events) == 80
    assert all(e.kind == "commit" for e in commit_events)

    # 2. PRs
    prs_data = json.loads((DATA_DIR / "pull_requests.json").read_text(encoding="utf-8"))
    pr_events = list(PullRequestsLoader().load(prs_data))
    assert len(pr_events) == 25
    assert all(e.kind == "pull_request" for e in pr_events)

    # 3. Branches
    branches_data = json.loads((DATA_DIR / "branches.json").read_text(encoding="utf-8"))
    branch_events = list(BranchesLoader().load(branches_data))
    assert len(branch_events) == 5
    assert all(e.kind == "branch" for e in branch_events)

    # 4. Issues
    issues_data = json.loads((DATA_DIR / "issues.json").read_text(encoding="utf-8"))
    issue_events = list(IssuesLoader().load(issues_data))
    assert len(issue_events) == 25
    assert all(e.kind == "issue" for e in issue_events)

    # 5. Slack
    bk_data = json.loads((DATA_DIR / "slack_backend-dev.json").read_text(encoding="utf-8"))
    bk_events = list(SlackLoader().load(bk_data))
    assert len(bk_events) == 18

    leads_data = json.loads((DATA_DIR / "slack_leads-private.json").read_text(encoding="utf-8"))
    leads_events = list(SlackLoader().load(leads_data))
    assert len(leads_events) == 7
    assert all(e.acl_hint == "confidential" for e in leads_events)

    inc_data = json.loads((DATA_DIR / "slack_incidents.json").read_text(encoding="utf-8"))
    inc_events = list(SlackLoader().load(inc_data))
    assert len(inc_events) == 6

    # 6. Markdown docs
    doc_events = []
    m_loader = MarkdownLoader()
    for doc_path in DOCS_DIR.glob("*.md"):
        doc_events.extend(list(m_loader.load(doc_path)))
    assert len(doc_events) == 5

    total = (
        len(commit_events)
        + len(pr_events)
        + len(branch_events)
        + len(issue_events)
        + len(bk_events)
        + len(leads_events)
        + len(inc_events)
        + len(doc_events)
    )
    assert total == 171


def test_slack_thread_per_message_offsets() -> None:
    leads_data = json.loads((DATA_DIR / "slack_leads-private.json").read_text(encoding="utf-8"))
    events = list(SlackLoader().load(leads_data))

    # Check vendor escalation thread
    escalation_ev = next(e for e in events if e.external_id == "slack_th_leads_vendor_escalation")
    messages = escalation_ev.meta.get("messages", [])
    assert len(messages) == 2

    # Verify character slicing points exactly to message text
    root_msg = messages[0]
    extracted = escalation_ev.body[root_msg["char_start"] : root_msg["char_end"]]
    assert "David Vance" in extracted
    assert root_msg["user"] == "aarav.k"


def test_markdown_inference() -> None:
    loader = MarkdownLoader()

    # ADR doc
    adr_events = list(loader.load(DOCS_DIR / "ADR-003-caching.md"))
    assert len(adr_events) == 1
    assert adr_events[0].kind == "adr_doc"
    assert "Redis" in adr_events[0].title
    assert adr_events[0].external_id == "ADR-003"

    # Runbook
    rb_events = list(loader.load(DOCS_DIR / "runbook-webhooks.md"))
    assert len(rb_events) == 1
    assert rb_events[0].kind == "runbook"

    # Meeting note
    meeting_events = list(loader.load(DOCS_DIR / "meeting-note-2026-10-14.md"))
    assert len(meeting_events) == 1
    assert meeting_events[0].kind == "meeting_note"


def test_normalizer_authority_and_sensitivity_rules(session: Session) -> None:
    # Authority rules
    assert compute_authority("commit", {}) == 1.0
    assert compute_authority("pull_request", {"status": "merged"}) == 1.0
    assert compute_authority("pull_request", {"status": "open"}) == 0.5
    assert compute_authority("pull_request", {"status": "closed"}) == 0.5
    assert compute_authority("issue", {}) == 0.8
    assert compute_authority("adr_doc", {}) == 0.6
    assert compute_authority("chat_thread", {}) == 0.4
    assert compute_authority("branch", {}) == 0.5

    # Sensitivity rules
    assert compute_sensitivity("public", {}) == 0
    assert compute_sensitivity("internal", {}) == 1
    assert compute_sensitivity(None, {}) == 1
    assert compute_sensitivity("confidential", {}) == 2
    assert compute_sensitivity("restricted", {}) == 3
    assert compute_sensitivity(None, {"sensitivity": 2}) == 2


def test_resync_idempotency_and_version_history(session: Session) -> None:
    proj = Project(name="TestProj", slug="testproj")
    session.add(proj)
    session.commit()

    src = Source(project_id=proj.id, type="github", name="TestRepo")
    session.add(src)
    session.commit()

    ev1 = RawEvent(
        kind="commit",
        external_id="c_test_01",
        source_uri="https://github.com/test/commit/01",
        title="Initial commit",
        body="Initial body text",
        author_alias="aarav",
        occurred_at=session.exec(select(Project)).first().created_at,
        meta={"sha": "c_test_01"},
    )

    art1 = normalize_and_upsert_event(session, project_id=proj.id, source_id=src.id, event=ev1)
    session.commit()
    assert art1.title == "Initial commit"
    first_id = art1.id

    # Same event upserted again -> no duplication
    art2 = normalize_and_upsert_event(session, project_id=proj.id, source_id=src.id, event=ev1)
    session.commit()
    assert art2.id == first_id

    # Updated body -> updates artifact and preserves history
    ev1_updated = RawEvent(
        kind="commit",
        external_id="c_test_01",
        source_uri="https://github.com/test/commit/01",
        title="Initial commit updated",
        body="Modified body text with new details",
        author_alias="aarav",
        occurred_at=ev1.occurred_at,
        meta={"sha": "c_test_01"},
    )
    art3 = normalize_and_upsert_event(session, project_id=proj.id, source_id=src.id, event=ev1_updated)
    session.commit()
    assert art3.id == first_id
    assert art3.title == "Initial commit updated"
    assert "history" in art3.meta
    assert len(art3.meta["history"]) == 1


def test_upload_validation_limits(client: TestClient) -> None:
    headers = get_auth_headers(client)

    with Session(get_engine()) as session:
        proj = Project(name="UploadProj", slug="uploadproj")
        session.add(proj)
        session.commit()
        session.refresh(proj)
        proj_id = proj.id

    # 1. Invalid file extension rejected (400)
    bad_file = ("bad_script.py", b"print('hello')", "text/x-python")
    bad_resp = client.post(
        f"/api/v1/projects/{proj_id}/sources/upload",
        headers=headers,
        files={"file": bad_file},
    )
    assert bad_resp.status_code == 400
    assert bad_resp.json()["error"]["code"] == "BAD_REQUEST"

    # 2. Oversize file rejected (413)
    huge_data = b"x" * (21 * 1024 * 1024)  # 21MB > 20MB
    huge_file = ("huge_data.json", huge_data, "application/json")
    huge_resp = client.post(
        f"/api/v1/projects/{proj_id}/sources/upload",
        headers=headers,
        files={"file": huge_file},
    )
    assert huge_resp.status_code == 413
    assert huge_resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

    # 3. Valid file upload succeeds (201)
    valid_file = ("notes.md", b"# Architecture Notes\nSome content here.", "text/markdown")
    ok_resp = client.post(
        f"/api/v1/projects/{proj_id}/sources/upload",
        headers=headers,
        files={"file": valid_file},
    )
    assert ok_resp.status_code == 201
    source_data = ok_resp.json()
    assert source_data["name"] == "notes.md"
    assert source_data["type"] == "markdown"


def test_demo_load_endpoint_creates_artifacts_matching_ground_truth(client: TestClient) -> None:
    headers = get_auth_headers(client)

    # Call demo load endpoint
    resp = client.post("/api/v1/demo/load", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["total_artifacts"] == 171

    # Verify counts match ground truth
    gt = json.loads((SEED_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    expected_counts = gt["artifact_counts"]
    assert data["total_artifacts"] == expected_counts["total_artifacts"]

    # Verify database contents
    with Session(get_engine()) as session:
        artifacts = session.exec(select(Artifact).where(Artifact.project_id == data["project_id"])).all()
        assert len(artifacts) == 171

        # Check unique kinds
        kinds = {a.kind for a in artifacts}
        assert "commit" in kinds
        assert "pull_request" in kinds
        assert "issue" in kinds
        assert "branch" in kinds
        assert "chat_thread" in kinds
        assert "adr_doc" in kinds

        # Check demo users seeded
        users = session.exec(select(User)).all()
        user_emails = {u.email for u in users}
        assert "aarav@payflow.dev" in user_emails
        assert "meera@payflow.dev" in user_emails
        assert "kabir@payflow.dev" in user_emails

    # Idempotent: re-calling demo/load does not duplicate artifacts
    resp2 = client.post("/api/v1/demo/load", headers=headers)
    assert resp2.status_code == 200
    with Session(get_engine()) as session:
        artifacts2 = session.exec(select(Artifact).where(Artifact.project_id == data["project_id"])).all()
        assert len(artifacts2) == 171
