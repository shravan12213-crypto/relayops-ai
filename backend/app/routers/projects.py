"""Projects router: project listing, creation, and detail retrieval."""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, status
from sqlmodel import Session, select

from ..auth import get_current_user
from ..db import get_session
from ..errors import AppError
from ..models import Project, ProjectMember, User
from ..schemas import ProjectCreate, ProjectRead

router = APIRouter(tags=["projects"])
logger = logging.getLogger("relayops.routers.projects")


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[ProjectRead]:
    """List all projects accessible to the current user."""
    if current_user.role in ("lead", "auditor"):
        projects = session.exec(select(Project).order_by(Project.created_at.desc())).all()
    else:
        member_project_ids = set(
            session.exec(
                select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id)
            ).all()
        )
        if not member_project_ids:
            return []
        projects = session.exec(
            select(Project).where(Project.id.in_(member_project_ids)).order_by(Project.created_at.desc())
        ).all()

    return [ProjectRead.model_validate(p) for p in projects]


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    """Retrieve project details by ID."""
    project = session.get(Project, project_id)
    if not project:
        raise AppError("NOT_FOUND", "Project not found", status_code=404)

    # Check project membership unless role is lead or auditor
    if current_user.role not in ("lead", "auditor"):
        member = session.exec(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.id,
            )
        ).first()
        if not member:
            raise AppError(
                "FORBIDDEN", "Access denied: you are not a member of this project", status_code=403
            )

    return ProjectRead.model_validate(project)


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    """Create a new project. Allowed for lead users."""
    if current_user.role != "lead":
        raise AppError("FORBIDDEN", "Only team leads can create new projects", status_code=403)

    raw_slug = payload.slug or re.sub(r"[^a-z0-9_-]+", "-", payload.name.lower()).strip("-")
    slug = raw_slug or "project"

    existing = session.exec(select(Project).where(Project.slug == slug)).first()
    if existing:
        raise AppError("CONFLICT", f"Project with slug '{slug}' already exists", status_code=409)

    project = Project(
        name=payload.name,
        slug=slug,
        description=payload.description,
        repo_url=payload.repo_url,
    )
    session.add(project)
    session.commit()
    session.refresh(project)

    member = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        project_role="lead",
    )
    session.add(member)
    session.commit()

    logger.info("Created project %s (%s) by user %s", project.id, project.name, current_user.id)
    return ProjectRead.model_validate(project)
