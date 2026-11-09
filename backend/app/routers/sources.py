"""Sources router: source configuration, file uploads, background sync, and demo dataset loader."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlmodel import Session, select

from ..auth import get_current_user, hash_password
from ..config import BACKEND_DIR, get_settings
from ..db import audit, get_session, utcnow
from ..errors import AppError
from ..ingest.base import RawEvent
from ..ingest.github import GitHubLiveLoader
from ..ingest.json_loaders import (
    BranchesLoader,
    CommitsLoader,
    IssuesLoader,
    PullRequestsLoader,
    SlackLoader,
)
from ..ingest.markdown import MarkdownLoader
from ..ingest.normalize import normalize_and_upsert_event
from ..ingest.redact import redact
from ..models import Artifact, Job, Project, ProjectMember, RedactionEvent, Source, User
from ..schemas import (
    ArtifactRead,
    DemoLoadResponse,
    JobRead,
    RedactionAuditResponse,
    RedactionRuleSummary,
    SourceCreate,
    SourceRead,
    StatusResponse,
)

router = APIRouter(tags=["sources"])
logger = logging.getLogger("relayops.routers.sources")

ALLOWED_EXTENSIONS = {".json", ".md", ".txt", ".pdf"}
UPLOAD_DIR = BACKEND_DIR / "data" / "uploads"
SEED_DATA_DIR = BACKEND_DIR / "seed" / "data"
SEED_DOCS_DIR = SEED_DATA_DIR / "docs"


def sync_source_worker(source_id: str, job_id: str) -> None:
    """Background worker executing source synchronization and logging progress."""
    from ..db import get_engine

    engine = get_engine()
    with Session(engine) as session:
        source = session.get(Source, source_id)
        job = session.get(Job, job_id)
        if not source or not job:
            return

        job.status = "running"
        job.stage = "fetching"
        job.progress = 10
        job.log.append({"ts": utcnow().isoformat(), "message": f"Starting sync for source {source.name}"})
        session.add(job)
        session.commit()

        try:
            events: list[RawEvent] = []
            stype = source.type
            cfg = source.config

            if stype == "github":
                repo = cfg.get("repo", "")
                token = cfg.get("token")
                loader = GitHubLiveLoader(token=token)
                events.extend(loader.load(repo, max_items=cfg.get("max_items", 100)))

            elif stype in ("json", "file", "commits", "pull_requests", "branches", "issues", "slack"):
                file_path_str = cfg.get("file_path")
                if not file_path_str or not Path(file_path_str).exists():
                    raise RuntimeError(f"Configured file path does not exist: {file_path_str}")
                p = Path(file_path_str)
                raw_text = p.read_text(encoding="utf-8")

                if "commits" in p.name.lower() or stype == "commits":
                    events.extend(CommitsLoader().load(raw_text))
                elif "pull_requests" in p.name.lower() or stype == "pull_requests":
                    events.extend(PullRequestsLoader().load(raw_text))
                elif "branches" in p.name.lower() or stype == "branches":
                    events.extend(BranchesLoader().load(raw_text))
                elif "issues" in p.name.lower() or stype == "issues":
                    events.extend(IssuesLoader().load(raw_text))
                elif "slack" in p.name.lower() or stype == "slack":
                    events.extend(SlackLoader().load(raw_text))

            elif stype == "markdown":
                file_path_str = cfg.get("file_path")
                if file_path_str and Path(file_path_str).exists():
                    events.extend(MarkdownLoader().load(Path(file_path_str)))

            job.stage = "normalizing"
            job.progress = 50
            job.log.append(
                {
                    "ts": utcnow().isoformat(),
                    "message": f"Fetched {len(events)} events; normalizing artifacts",
                }
            )
            session.add(job)
            session.commit()

            count = 0
            for ev in events:
                normalize_and_upsert_event(
                    session,
                    project_id=source.project_id,
                    source_id=source.id,
                    event=ev,
                )
                count += 1

            source.last_synced_at = utcnow()
            source.stats = {"artifacts_count": count}
            source.status = "ready"
            session.add(source)

            job.status = "done"
            job.progress = 100
            job.stage = "complete"
            job.log.append(
                {"ts": utcnow().isoformat(), "message": f"Successfully ingested {count} artifacts"}
            )
            session.add(job)
            session.commit()

            logger.info("Source %s (%s) synced: %d artifacts", source.name, source.id, count)

        except Exception as exc:
            logger.exception("Sync failed for source %s: %s", source.id, exc)
            job.status = "failed"
            job.error = str(exc)
            job.log.append({"ts": utcnow().isoformat(), "message": f"Sync failed: {exc}"})
            source.status = "error"
            session.add(source)
            session.add(job)
            session.commit()


@router.post("/projects/{project_id}/sources", response_model=SourceRead, status_code=201)
def create_source(
    project_id: str,
    payload: SourceCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SourceRead:
    """Register a new source configuration for a project."""
    project = session.get(Project, project_id)
    if not project:
        raise AppError("NOT_FOUND", "Project not found", status_code=404)

    source = Source(
        project_id=project_id,
        type=payload.type,
        name=payload.name,
        config=payload.config,
        status="ready",
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    audit(
        session,
        actor_id=current_user.id,
        action="CREATE_SOURCE",
        target_type="source",
        target_id=source.id,
        payload={"name": source.name, "type": source.type},
    )
    session.commit()

    return SourceRead.model_validate(source)


@router.post("/projects/{project_id}/sources/upload", response_model=SourceRead, status_code=201)
async def upload_source_file(
    project_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SourceRead:
    """Upload a file as a new data source with strict size and extension checks."""
    settings = get_settings()
    project = session.get(Project, project_id)
    if not project:
        raise AppError("NOT_FOUND", "Project not found", status_code=404)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError(
            "BAD_REQUEST",
            f"Unsupported file type '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            status_code=400,
        )

    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise AppError(
            "PAYLOAD_TOO_LARGE",
            f"File exceeds maximum upload size of {settings.max_upload_mb}MB",
            status_code=413,
        )

    # Save to uploads dir
    dest_dir = UPLOAD_DIR / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = Path(file.filename or "uploaded_file.txt").name
    dest_path = dest_dir / safe_filename
    dest_path.write_bytes(content)

    inferred_type = "markdown" if ext in (".md", ".txt", ".pdf") else "json"
    source = Source(
        project_id=project_id,
        type=inferred_type,
        name=file.filename or safe_filename,
        config={"file_path": str(dest_path), "original_name": file.filename},
        status="ready",
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    audit(
        session,
        actor_id=current_user.id,
        action="UPLOAD_SOURCE_FILE",
        target_type="source",
        target_id=source.id,
        payload={"filename": file.filename, "size_bytes": len(content)},
    )
    session.commit()

    return SourceRead.model_validate(source)


@router.get("/projects/{project_id}/sources", response_model=list[SourceRead])
def list_project_sources(
    project_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> list[SourceRead]:
    """List all active sources registered under a project."""
    sources = session.exec(
        select(Source).where(Source.project_id == project_id, Source.status != "deleted")
    ).all()
    return [SourceRead.model_validate(s) for s in sources]


@router.get("/sources", response_model=list[SourceRead])
def list_all_sources(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> list[SourceRead]:
    """List all sources across projects."""
    sources = session.exec(select(Source).where(Source.status != "deleted")).all()
    return [SourceRead.model_validate(s) for s in sources]


@router.get("/sources/{source_id}", response_model=SourceRead)
def get_source(
    source_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> SourceRead:
    source = session.get(Source, source_id)
    if not source or source.status == "deleted":
        raise AppError("NOT_FOUND", "Source not found", status_code=404)
    return SourceRead.model_validate(source)


@router.post("/sources/{source_id}/sync", response_model=JobRead)
def sync_source(
    source_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    sync_inline: bool = False,
) -> JobRead:
    """Trigger synchronization for a data source, running as a background task."""
    source = session.get(Source, source_id)
    if not source or source.status == "deleted":
        raise AppError("NOT_FOUND", "Source not found", status_code=404)

    job = Job(
        project_id=source.project_id,
        kind="source_sync",
        status="queued",
        progress=0,
        stage="queued",
        log=[{"ts": utcnow().isoformat(), "message": f"Sync queued for source {source.name}"}],
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    if sync_inline:
        sync_source_worker(source.id, job.id)
        session.refresh(job)
    else:
        background_tasks.add_task(sync_source_worker, source.id, job.id)

    audit(
        session,
        actor_id=current_user.id,
        action="SYNC_SOURCE",
        target_type="source",
        target_id=source.id,
        payload={"job_id": job.id},
    )
    session.commit()

    return JobRead.model_validate(job)


@router.delete("/sources/{source_id}", response_model=StatusResponse)
def delete_source(
    source_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> StatusResponse:
    """Soft delete a source."""
    source = session.get(Source, source_id)
    if not source or source.status == "deleted":
        raise AppError("NOT_FOUND", "Source not found", status_code=404)

    source.status = "deleted"
    session.add(source)
    session.commit()

    audit(
        session,
        actor_id=current_user.id,
        action="DELETE_SOURCE",
        target_type="source",
        target_id=source.id,
    )
    session.commit()
    return StatusResponse(ok=True)


# ---------------------------------------------------------------------------
# One-click "Load PayFlow demo dataset" endpoint
# ---------------------------------------------------------------------------


def execute_demo_load(
    session: Session, current_user_id: str | None = None
) -> tuple[Project, dict[str, int], int]:
    """Load the full PayFlow demo dataset into the database."""
    # 1. Ensure PayFlow project exists
    project = session.exec(select(Project).where(Project.slug == "payflow")).first()
    if not project:
        project = Project(
            name="PayFlow",
            slug="payflow",
            description="Payment webhook infrastructure & transaction ledger.",
            repo_url="https://github.com/payflow/payflow",
            status="active",
        )
        session.add(project)
        session.commit()
        session.refresh(project)

    # 2. Seed 5 demo users from users.json if not present
    users_file = SEED_DATA_DIR / "users.json"
    if users_file.exists():
        users_data = json.loads(users_file.read_text(encoding="utf-8"))
        for u_seed in users_data:
            existing_user = session.exec(select(User).where(User.email == u_seed["email"].lower())).first()
            if not existing_user:
                new_user = User(
                    email=u_seed["email"].lower(),
                    name=u_seed["name"],
                    password_hash=hash_password(u_seed["password"]),
                    role=u_seed["role"],
                    clearance=u_seed["clearance"],
                    is_active=True,
                )
                session.add(new_user)
                session.flush()

                # Project member
                pm = ProjectMember(
                    project_id=project.id,
                    user_id=new_user.id,
                    project_role="lead" if u_seed["role"] == "lead" else "contributor",
                )
                session.add(pm)

    # 3. Create canonical sources
    sources: dict[str, Source] = {}
    source_specs = [
        ("github", "github", "PayFlow GitHub Repository"),
        ("slack", "slack_json", "PayFlow Slack Channels"),
        ("docs", "markdown", "PayFlow Architecture Docs"),
        ("jira", "jira_json", "PayFlow Jira Issues"),
    ]
    for key, stype, sname in source_specs:
        src = session.exec(
            select(Source).where(Source.project_id == project.id, Source.name == sname)
        ).first()
        if not src:
            src = Source(
                project_id=project.id,
                type=stype,
                name=sname,
                config={"seed": True},
                status="ready",
            )
            session.add(src)
            session.flush()
        sources[key] = src

    counts: dict[str, int] = {}

    def _ingest_events(src: Source, events: list[RawEvent]) -> None:
        for ev in events:
            normalize_and_upsert_event(
                session,
                project_id=project.id,
                source_id=src.id,
                event=ev,
            )
            counts[ev.kind] = counts.get(ev.kind, 0) + 1

    # Ingest branches
    branches_file = SEED_DATA_DIR / "branches.json"
    if branches_file.exists():
        evs = list(BranchesLoader().load(branches_file.read_text(encoding="utf-8")))
        _ingest_events(sources["github"], evs)

    # Ingest commits
    commits_file = SEED_DATA_DIR / "commits.json"
    if commits_file.exists():
        evs = list(CommitsLoader().load(commits_file.read_text(encoding="utf-8")))
        _ingest_events(sources["github"], evs)

    # Ingest PRs
    prs_file = SEED_DATA_DIR / "pull_requests.json"
    if prs_file.exists():
        evs = list(PullRequestsLoader().load(prs_file.read_text(encoding="utf-8")))
        _ingest_events(sources["github"], evs)

    # Ingest issues
    issues_file = SEED_DATA_DIR / "issues.json"
    if issues_file.exists():
        evs = list(IssuesLoader().load(issues_file.read_text(encoding="utf-8")))
        _ingest_events(sources["jira"], evs)

    # Ingest Slack channels
    for sf in ["slack_backend-dev.json", "slack_leads-private.json", "slack_incidents.json"]:
        p = SEED_DATA_DIR / sf
        if p.exists():
            evs = list(SlackLoader().load(p.read_text(encoding="utf-8")))
            _ingest_events(sources["slack"], evs)

    # Ingest docs
    if SEED_DOCS_DIR.exists():
        m_loader = MarkdownLoader()
        for doc_file in SEED_DOCS_DIR.glob("*.md"):
            evs = list(m_loader.load(doc_file))
            _ingest_events(sources["docs"], evs)

    session.commit()

    total = sum(counts.values())

    audit(
        session,
        actor_id=current_user_id,
        action="LOAD_DEMO_DATASET",
        target_type="project",
        target_id=project.id,
        payload={"total_artifacts": total, "counts": counts},
    )
    session.commit()

    return project, counts, total


@router.post("/projects/{project_id}/demo-load", response_model=DemoLoadResponse)
def load_demo_dataset_for_project(
    project_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DemoLoadResponse:
    """Load the PayFlow seed dataset into the specified project."""
    project = session.get(Project, project_id)
    if not project:
        raise AppError("NOT_FOUND", "Project not found", status_code=404)

    proj, counts, total = execute_demo_load(session, current_user.id)
    return DemoLoadResponse(
        status="ok",
        project_id=proj.id,
        counts=counts,
        total_artifacts=total,
    )


@router.post("/demo/load", response_model=DemoLoadResponse)
def load_demo_dataset_global(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DemoLoadResponse:
    """One-click endpoint to initialize and load the PayFlow demo dataset."""
    proj, counts, total = execute_demo_load(session, current_user.id)
    return DemoLoadResponse(
        status="ok",
        project_id=proj.id,
        counts=counts,
        total_artifacts=total,
    )


# ---------------------------------------------------------------------------
# Redaction Transparency & Audit Endpoints
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/redaction-audit", response_model=RedactionAuditResponse)
def get_redaction_audit(
    project_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> RedactionAuditResponse:
    """Retrieve transparency report of redaction rules triggered for this project."""
    project = session.get(Project, project_id)
    if not project:
        raise AppError("NOT_FOUND", "Project not found", status_code=404)

    # Query all RedactionEvent rows for artifacts in this project
    query = (
        select(RedactionEvent)
        .join(Artifact, Artifact.id == RedactionEvent.artifact_id)
        .where(Artifact.project_id == project_id)
    )
    events = session.exec(query).all()

    rule_counts: dict[str, int] = {}
    rule_samples: dict[str, str] = {}
    for ev in events:
        rule_counts[ev.rule] = rule_counts.get(ev.rule, 0) + ev.count
        if ev.rule not in rule_samples and ev.sample_masked:
            rule_samples[ev.rule] = ev.sample_masked

    rules = [
        RedactionRuleSummary(
            rule=r,
            count=count,
            sample_masked=rule_samples.get(r, "[REDACTED]"),
        )
        for r, count in sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    total = sum(r.count for r in rules)
    return RedactionAuditResponse(rules=rules, total_redactions=total)


@router.post("/projects/{project_id}/redact-rescan", response_model=RedactionAuditResponse)
def rescan_project_redactions(
    project_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RedactionAuditResponse:
    """Re-run redaction rules across all artifacts for this project and refresh audit records."""
    project = session.get(Project, project_id)
    if not project:
        raise AppError("NOT_FOUND", "Project not found", status_code=404)

    artifacts = session.exec(select(Artifact).where(Artifact.project_id == project_id)).all()
    for art in artifacts:
        # Delete old redaction events
        old_events = session.exec(select(RedactionEvent).where(RedactionEvent.artifact_id == art.id)).all()
        for ev in old_events:
            session.delete(ev)

        # Run fresh redaction
        res = redact(art.body_raw)
        art.body_redacted = res.text
        art.redaction_count = len(res.events)
        session.add(art)

        for rev in res.events:
            new_ev = RedactionEvent(
                artifact_id=art.id,
                rule=rev["rule"],
                count=rev.get("count", 1),
                sample_masked=rev.get("sample_masked", "[REDACTED]"),
            )
            session.add(new_ev)

    audit(
        session,
        actor_id=current_user.id,
        action="RESCAN_REDACTIONS",
        target_type="project",
        target_id=project_id,
        payload={"artifacts_rescanned": len(artifacts)},
    )
    session.commit()

    return get_redaction_audit(project_id, session, current_user)


@router.get("/artifacts/{artifact_id}", response_model=ArtifactRead)
def get_artifact(
    artifact_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> ArtifactRead:
    """Retrieve artifact details and redacted text by artifact ID."""
    art = session.get(Artifact, artifact_id)
    if not art:
        raise AppError("NOT_FOUND", "Artifact not found", status_code=404)
    return ArtifactRead.model_validate(art)
