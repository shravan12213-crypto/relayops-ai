"""Router for governance, audit chain verification, policy matrix,
project members management, and system admin operations.

Enforces:
- Lead and Auditor role boundaries on compliance/audit endpoints.
- Lead-only permissions for member management and danger-zone resets.
- Cryptographic hash chain verification for tamper detection.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlmodel import Session, col, func, select

from app.auth import get_current_user
from app.config import get_settings
from app.db import (
    audit,
    get_project_by_id_or_slug,
    get_session,
    utcnow,
    verify_audit_chain_detailed,
)
from app.errors import AppError
from app.models import (
    Artifact,
    AuditLog,
    Claim,
    Handover,
    Project,
    ProjectMember,
    User,
)
from app.policy import allowed_actions, can_view_artifact, effective_clearance
from app.routers.sources import execute_demo_load
from app.schemas import (
    AuditChainVerifyResponse,
    AuditLogRead,
    AuditLogsPaginated,
    PolicyMatrixResponse,
    PolicyMatrixRule,
    ProjectMemberCreateInput,
    ProjectMemberRead,
    ProjectMemberUpdateInput,
    ResetDemoResponse,
    SensitivityBucket,
    SensitivityDistributionResponse,
    SystemStatusResponse,
)

logger = logging.getLogger("relayops.routers.governance")
router = APIRouter(tags=["governance"])


# ---------------------------------------------------------------------------
# 1. Audit Log & Chain Verification Endpoints
# ---------------------------------------------------------------------------


@router.get("/audit/logs", response_model=Any)
def list_governance_audit_logs(
    response: Response,
    actor_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int | None = Query(default=None, ge=0),
    paged: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve filtered, paginated cryptographic audit logs. Restricted to lead and auditor."""
    if current_user.role not in ("lead", "auditor"):
        raise AppError("FORBIDDEN", "Access to audit logs requires Lead or Auditor role", status_code=403)

    eff_limit = limit if limit is not None else page_size
    eff_offset = offset if offset is not None else (page - 1) * page_size
    eff_page = (eff_offset // eff_limit) + 1 if eff_limit else 1

    query = select(AuditLog)
    count_query = select(func.count(col(AuditLog.seq)))

    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
        count_query = count_query.where(AuditLog.actor_id == actor_id)

    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
        count_query = count_query.where(AuditLog.action.ilike(f"%{action}%"))

    if from_date:
        try:
            dt_from = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            query = query.where(AuditLog.created_at >= dt_from)
            count_query = count_query.where(AuditLog.created_at >= dt_from)
        except ValueError:
            pass

    if to_date:
        try:
            dt_to = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            query = query.where(AuditLog.created_at <= dt_to)
            count_query = count_query.where(AuditLog.created_at <= dt_to)
        except ValueError:
            pass

    total = session.exec(count_query).one() or 0
    items = session.exec(query.order_by(AuditLog.seq.desc()).offset(eff_offset).limit(eff_limit)).all()

    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(eff_page)
    response.headers["X-Page-Size"] = str(eff_limit)

    validated_items = [AuditLogRead.model_validate(item) for item in items]
    if paged:
        pages = max(1, -(-total // eff_limit)) if eff_limit else 1
        return AuditLogsPaginated(
            items=validated_items,
            total=total,
            page=eff_page,
            page_size=eff_limit,
            pages=pages,
        )
    return validated_items


@router.post("/audit/verify-chain", response_model=AuditChainVerifyResponse)
def verify_audit_hash_chain(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AuditChainVerifyResponse:
    """Verify cryptographic SHA-256 hash chain sequence of audit records."""
    if current_user.role not in ("lead", "auditor"):
        raise AppError("FORBIDDEN", "Chain verification requires Lead or Auditor role", status_code=403)

    res = verify_audit_chain_detailed(session)
    return AuditChainVerifyResponse(
        valid=res["valid"],
        entries_count=res["entries_count"],
        tampered_seq=res["tampered_seq"],
        error=res["error"],
    )


# ---------------------------------------------------------------------------
# 2. Policy Matrix Endpoint
# ---------------------------------------------------------------------------


@router.get("/policy", response_model=PolicyMatrixResponse)
def get_policy_matrix(
    _: User = Depends(get_current_user),
) -> PolicyMatrixResponse:
    """Retrieve full role x clearance permissions matrix derived from policy.py."""
    roles = ["lead", "outgoing", "successor", "contractor", "auditor"]
    clearances = [
        {"level": 0, "name": "Public", "description": "Open source, public repositories and licenses"},
        {
            "level": 1,
            "name": "Internal",
            "description": "Standard company-wide engineering artifacts and PRs",
        },
        {
            "level": 2,
            "name": "Confidential",
            "description": "Partner credentials, vendor pricing, escalation contacts",
        },
        {
            "level": 3,
            "name": "Restricted",
            "description": "Executive sign-offs, legal matters, security vault keys",
        },
    ]

    rules: list[PolicyMatrixRule] = []

    for r in roles:
        for c in clearances:
            lvl = c["level"]
            dummy_user = {"role": r, "clearance": lvl, "id": "dummy"}
            eff_c = effective_clearance(dummy_user)
            actions = allowed_actions(dummy_user)

            # Artifact bodies
            artifact_visible = can_view_artifact(
                dummy_user, {"sensitivity": lvl, "project_id": "p1"}, ["dummy"]
            )

            notes = []
            if r == "contractor" and lvl > 1:
                notes.append("Clearance capped at Level 1 per contractor policy")
            elif r == "auditor":
                notes.append("Clearance capped at Level 1; raw artifact text systematically withheld")
            elif r == "lead":
                notes.append("Administrative sign-off & delivery authority")

            rules.append(
                PolicyMatrixRule(
                    role=r,
                    clearance=lvl,
                    clearance_name=c["name"],
                    artifact_bodies_visible=artifact_visible,
                    claims_max_sensitivity=eff_c,
                    can_signoff="signoff" in actions,
                    can_deliver="deliver" in actions,
                    can_view_audit="view_audit_log" in actions,
                    can_manage_members="manage_members" in actions,
                    notes="; ".join(notes) if notes else "Standard role access",
                )
            )

    return PolicyMatrixResponse(
        roles=roles,
        clearance_levels=clearances,
        rules=rules,
    )


# ---------------------------------------------------------------------------
# 3. Sensitivity Distribution Report
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/sensitivity-distribution", response_model=SensitivityDistributionResponse)
def get_sensitivity_distribution(
    project_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> SensitivityDistributionResponse:
    """Retrieve sensitivity level breakdown for artifacts and claims in this project."""
    project = get_project_by_id_or_slug(session, project_id)
    if not project:
        raise AppError("NOT_FOUND", "Project not found", status_code=404)

    # 1. Query artifacts by sensitivity
    art_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    arts = session.exec(
        select(Artifact.sensitivity, func.count(Artifact.id))
        .where(Artifact.project_id == project.id)
        .group_by(Artifact.sensitivity)
    ).all()
    for s_level, cnt in arts:
        art_counts[int(s_level)] = cnt

    # 2. Query claims by sensitivity
    claim_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    cls = session.exec(
        select(Claim.sensitivity, func.count(Claim.id))
        .where(Claim.project_id == project_id)
        .group_by(Claim.sensitivity)
    ).all()
    for s_level, cnt in cls:
        claim_counts[int(s_level)] = cnt

    total_artifacts = sum(art_counts.values())
    total_claims = sum(claim_counts.values())
    grand_total = total_artifacts + total_claims

    level_names = {0: "Public (0)", 1: "Internal (1)", 2: "Confidential (2)", 3: "Restricted (3)"}
    buckets: list[SensitivityBucket] = []

    for lvl in range(4):
        a_cnt = art_counts.get(lvl, 0)
        c_cnt = claim_counts.get(lvl, 0)
        tot = a_cnt + c_cnt
        pct = round((tot / grand_total * 100), 1) if grand_total > 0 else 0.0
        buckets.append(
            SensitivityBucket(
                level=lvl,
                name=level_names[lvl],
                artifacts_count=a_cnt,
                claims_count=c_cnt,
                total_count=tot,
                percentage=pct,
            )
        )

    return SensitivityDistributionResponse(
        project_id=project_id,
        total_artifacts=total_artifacts,
        total_claims=total_claims,
        buckets=buckets,
    )


# ---------------------------------------------------------------------------
# 4. Project Members Management Endpoints (Lead Only)
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/members", response_model=list[ProjectMemberRead])
def list_project_members(
    project_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> list[ProjectMemberRead]:
    """List all members associated with a project."""
    project = get_project_by_id_or_slug(session, project_id)
    if not project:
        raise AppError("NOT_FOUND", "Project not found", status_code=404)

    rows = session.exec(
        select(ProjectMember, User)
        .join(User, ProjectMember.user_id == User.id)
        .where(ProjectMember.project_id == project.id)
        .order_by(ProjectMember.created_at.asc())
    ).all()

    result = []
    for pm, u in rows:
        result.append(
            ProjectMemberRead(
                id=pm.id,
                project_id=pm.project_id,
                user_id=pm.user_id,
                project_role=pm.project_role,
                user_name=u.name,
                user_email=u.email,
                user_role=u.role,
                user_clearance=u.clearance,
                created_at=pm.created_at,
            )
        )
    return result


@router.post(
    "/projects/{project_id}/members",
    response_model=ProjectMemberRead,
    status_code=status.HTTP_201_CREATED,
)
def add_project_member(
    project_id: str,
    payload: ProjectMemberCreateInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectMemberRead:
    """Add a user as a member of a project. Restricted strictly to project lead."""
    if current_user.role != "lead":
        raise AppError("FORBIDDEN", "Only project leads can add team members", status_code=403)

    project = get_project_by_id_or_slug(session, project_id)
    if not project:
        raise AppError("NOT_FOUND", "Project not found", status_code=404)

    target_user = session.get(User, payload.user_id)
    if not target_user:
        raise AppError("NOT_FOUND", "User not found", status_code=404)

    # Check if already a member
    existing = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == payload.user_id,
        )
    ).first()
    if existing:
        raise AppError("CONFLICT", "User is already a member of this project", status_code=409)

    # Update clearance if specified
    if payload.clearance is not None:
        if target_user.role in ("contractor", "auditor") and payload.clearance > 1:
            raise AppError(
                "VALIDATION_ERROR", f"Clearance for {target_user.role} cannot exceed Level 1", status_code=422
            )
        target_user.clearance = payload.clearance
        session.add(target_user)

    pm = ProjectMember(
        project_id=project.id,
        user_id=target_user.id,
        project_role=payload.project_role,
    )
    session.add(pm)

    audit(
        session,
        actor_id=current_user.id,
        action="project_member_added",
        target_type="project_member",
        target_id=pm.id,
        payload={"project_id": project_id, "user_id": target_user.id, "role": pm.project_role},
    )

    session.commit()
    session.refresh(pm)
    session.refresh(target_user)

    return ProjectMemberRead(
        id=pm.id,
        project_id=pm.project_id,
        user_id=pm.user_id,
        project_role=pm.project_role,
        user_name=target_user.name,
        user_email=target_user.email,
        user_role=target_user.role,
        user_clearance=target_user.clearance,
        created_at=pm.created_at,
    )


@router.patch("/projects/{project_id}/members/{user_id}", response_model=ProjectMemberRead)
def update_project_member(
    project_id: str,
    user_id: str,
    payload: ProjectMemberUpdateInput,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectMemberRead:
    """Update role or clearance of a project member. Restricted strictly to project lead."""
    if current_user.role != "lead":
        raise AppError("FORBIDDEN", "Only project leads can modify team member permissions", status_code=403)

    pm = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    ).first()
    if not pm:
        raise AppError("NOT_FOUND", "Project member record not found", status_code=404)

    target_user = session.get(User, user_id)
    if not target_user:
        raise AppError("NOT_FOUND", "User not found", status_code=404)

    if payload.project_role is not None:
        pm.project_role = payload.project_role
        pm.updated_at = utcnow()
        session.add(pm)

    if payload.clearance is not None:
        if target_user.role in ("contractor", "auditor") and payload.clearance > 1:
            raise AppError(
                "VALIDATION_ERROR", f"Clearance for {target_user.role} cannot exceed Level 1", status_code=422
            )
        target_user.clearance = payload.clearance
        session.add(target_user)

    audit(
        session,
        actor_id=current_user.id,
        action="project_member_updated",
        target_type="project_member",
        target_id=pm.id,
        payload={
            "project_id": project_id,
            "user_id": user_id,
            "new_role": pm.project_role,
            "new_clearance": target_user.clearance,
        },
    )

    session.commit()
    session.refresh(pm)
    session.refresh(target_user)

    return ProjectMemberRead(
        id=pm.id,
        project_id=pm.project_id,
        user_id=pm.user_id,
        project_role=pm.project_role,
        user_name=target_user.name,
        user_email=target_user.email,
        user_role=target_user.role,
        user_clearance=target_user.clearance,
        created_at=pm.created_at,
    )


@router.delete("/projects/{project_id}/members/{user_id}")
def remove_project_member(
    project_id: str,
    user_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Remove a user from project membership. Restricted strictly to project lead."""
    if current_user.role != "lead":
        raise AppError("FORBIDDEN", "Only project leads can remove team members", status_code=403)

    pm = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    ).first()
    if not pm:
        raise AppError("NOT_FOUND", "Project member record not found", status_code=404)

    session.delete(pm)
    audit(
        session,
        actor_id=current_user.id,
        action="project_member_removed",
        target_type="project_member",
        target_id=pm.id,
        payload={"project_id": project_id, "user_id": user_id},
    )
    session.commit()
    return {"status": "ok", "message": f"User {user_id} removed from project"}


# ---------------------------------------------------------------------------
# 5. System Status & Admin Danger Zone Endpoints
# ---------------------------------------------------------------------------


@router.get("/system/status", response_model=SystemStatusResponse)
def get_system_status(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> SystemStatusResponse:
    """Retrieve operational system status, active LLM mode, provider, and entity counts."""
    proj_cnt = session.exec(select(func.count(col(Project.id)))).one() or 0
    h_cnt = session.exec(select(func.count(col(Handover.id)))).one() or 0

    cfg = get_settings()
    return SystemStatusResponse(
        llm_mode=cfg.llm_mode,
        provider=cfg.llm_provider,
        model=cfg.active_model,
        environment=cfg.env,
        database="sqlite_wal" if cfg.is_sqlite else ("postgresql" if cfg.is_postgres else "unknown"),
        total_projects=proj_cnt,
        total_handovers=h_cnt,
    )


@router.post("/system/reset-demo", response_model=ResetDemoResponse)
def reset_demo_dataset_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ResetDemoResponse:
    """Danger Zone: Reset demo data. Restricted strictly to Lead and non-production environments."""
    if current_user.role != "lead":
        raise AppError("FORBIDDEN", "Only project leads can trigger a demo data reset", status_code=403)

    cfg = get_settings()
    if cfg.env == "prod":
        raise AppError("FORBIDDEN", "Reset demo data is disabled in production environments", status_code=403)

    proj, counts, total = execute_demo_load(session, current_user.id, seed_workflows=True)
    audit(
        session,
        actor_id=current_user.id,
        action="demo_reset",
        target_type="project",
        target_id=proj.id,
        payload={"total_artifacts": total, "counts": counts},
    )
    return ResetDemoResponse(
        status="ok",
        message="Demo dataset reset successfully.",
        project_id=proj.id,
        total_artifacts=total,
    )
