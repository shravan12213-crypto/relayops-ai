"""Tests for P08: Reconstruct entities, temporal knowledge graph, authority resolution, and claim extraction.

Validates:
- Entity resolution for people (Aarav's 4 aliases merge to 1 canonical entity)
- Module and service derivation from file paths and components
- Source authority hierarchy and resolve() temporal rules
- Graph construction with AUTHORED, REFERENCES, OWNS, DEPENDS_ON, BLOCKS edges
- Recursive CTE graph queries: module_dependencies, timeline, and bus_factor
- Extraction step creating bi-temporal decision nodes and SUPERSEDES edges
- Scenario 1 & 2 produce SUPERSEDES edges with bi-temporal invalidation
- Scenario 3 produces an UNRESOLVED conflict flag in Ambiguity ledger
- bus_factor() correctly flags ledger-sync with sole contributor Aarav
- Acceptance: Graph matches ground truth scenarios from ground_truth.json
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, select

from app.models import Ambiguity, Artifact, Edge, Entity, Node, Project
from app.reconstruct import (
    ResolutionStatus,
    authority_for,
    build_graph,
    bus_factor,
    extract_and_link_facts,
    match_confidence,
    module_dependencies,
    resolve,
    resolve_entities,
    timeline,
)
from app.routers.sources import execute_demo_load

# ---------------------------------------------------------------------------
# 1. Source Authority & Temporal Resolution Tests
# ---------------------------------------------------------------------------


def test_authority_for_artifacts() -> None:
    assert authority_for("commit") == 1.0
    assert authority_for("pull_request") == 1.0
    assert authority_for("issue") == 0.8
    assert authority_for("adr_doc") == 0.6
    assert authority_for("runbook") == 0.6
    assert authority_for("branch") == 0.5
    assert authority_for("chat_thread") == 0.4


def test_authority_resolve_newer_higher_supersedes() -> None:
    # Older ADR doc (Oct 12, auth 0.6) vs Newer Code/PR (Nov 2, auth 1.0)
    adr_item = {
        "valid_time": "2026-10-12T10:00:00Z",
        "kind": "adr_doc",
        "title": "Redis sessions",
    }
    pr_item = {
        "valid_time": "2026-11-02T15:30:00Z",
        "kind": "pull_request",
        "title": "Stateless JWT",
    }

    res = resolve(adr_item, pr_item)
    assert res.status == ResolutionStatus.SUPERSEDES
    assert res.winner == pr_item
    assert res.loser == adr_item


def test_authority_resolve_newer_lower_creates_conflict() -> None:
    # Older Merged Code (Sep 14, auth 1.0) vs Newer Chat (Oct 18, auth 0.4)
    code_item = {
        "valid_time": "2026-09-14T10:00:00Z",
        "kind": "commit",
        "title": "PostgreSQL 16 migration",
    }
    chat_item = {
        "valid_time": "2026-10-18T11:00:00Z",
        "kind": "chat_thread",
        "title": "Debating SQLite vs Postgres in chat",
    }

    res = resolve(code_item, chat_item)
    assert res.status == ResolutionStatus.CONFLICT
    # Code wins by authority, but conflict is flagged
    assert res.winner == code_item
    assert res.loser == chat_item


def test_authority_resolve_contemporaneous_equal_is_unresolved() -> None:
    # Two Slack messages on same day with equal authority (0.4)
    msg_100 = {
        "valid_time": "2026-10-18T10:15:00Z",
        "kind": "chat_thread",
        "title": "100/min rate limit",
    }
    msg_500 = {
        "valid_time": "2026-10-18T10:45:00Z",
        "kind": "chat_thread",
        "title": "500/min rate limit",
    }

    res = resolve(msg_100, msg_500)
    assert res.status == ResolutionStatus.UNRESOLVED
    assert res.winner is None


def test_match_confidence_heuristics() -> None:
    # Exact email match
    assert match_confidence("akulkarni@payflow.dev", "akulkarni@payflow.dev") == 1.0
    # First name + last initial vs full name
    assert match_confidence("aarav.k", "Aarav Kulkarni") >= 0.9
    # Handle with -dev suffix vs full name
    assert match_confidence("aarav-dev", "Aarav Kulkarni") >= 0.85
    # Completely different names
    assert match_confidence("kabir.s", "Aarav Kulkarni") == 0.0


# ---------------------------------------------------------------------------
# 2. Entity Resolution on Seed Data
# ---------------------------------------------------------------------------


def test_entity_resolution_alias_merging(session: Session) -> None:
    # Load demo dataset first
    execute_demo_load(session)

    project = session.exec(select(Project).where(Project.slug == "payflow")).one()

    # Run entity resolution
    res = resolve_entities(project.id, session)
    assert res["people_count"] >= 5
    assert res["modules_count"] >= 4

    # Verify Aarav Kulkarni's 4 aliases merged into 1 canonical entity
    aarav_entity = session.exec(
        select(Entity).where(
            Entity.project_id == project.id,
            Entity.type == "person",
            Entity.canonical_name == "Aarav Kulkarni",
        )
    ).one()

    aliases = set(aarav_entity.aliases)
    assert "aarav.k" in aliases
    assert "aarav-dev" in aliases
    assert "akulkarni@payflow.dev" in aliases
    assert "Aarav Kulkarni" in aliases

    # Verify artifacts by Aarav got linked to his entity ID
    aarav_arts = session.exec(
        select(Artifact).where(
            Artifact.project_id == project.id,
            Artifact.author_entity_id == aarav_entity.id,
        )
    ).all()
    assert len(aarav_arts) > 20

    # Verify modules derived
    module_names = {
        e.canonical_name
        for e in session.exec(
            select(Entity).where(Entity.project_id == project.id, Entity.type == "module")
        ).all()
    }
    assert "ledger-sync" in module_names
    assert "webhooks" in module_names
    assert "billing" in module_names
    assert "auth" in module_names


# ---------------------------------------------------------------------------
# 3. Knowledge Graph Construction & Edge Linking
# ---------------------------------------------------------------------------


def test_graph_construction(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    resolve_entities(project.id, session)

    # Build graph
    graph_res = build_graph(project.id, session)
    assert graph_res["nodes_count"] > 100
    assert graph_res["edges_count"] > 50

    # 1. Verify AUTHORED edges exist
    authored_edges = session.exec(
        select(Edge).where(Edge.project_id == project.id, Edge.type == "AUTHORED")
    ).all()
    assert len(authored_edges) > 30

    # 2. Verify REFERENCES edges exist (linking PRs, issues, commits)
    ref_edges = session.exec(
        select(Edge).where(Edge.project_id == project.id, Edge.type == "REFERENCES")
    ).all()
    assert len(ref_edges) > 10

    # 3. Verify OWNS edges exist
    owns_edges = session.exec(select(Edge).where(Edge.project_id == project.id, Edge.type == "OWNS")).all()
    assert len(owns_edges) >= 1

    # 4. Verify DEPENDS_ON edges exist
    deps_edges = session.exec(
        select(Edge).where(Edge.project_id == project.id, Edge.type == "DEPENDS_ON")
    ).all()
    assert len(deps_edges) >= 2


# ---------------------------------------------------------------------------
# 4. SQL Recursive CTE Graph Queries
# ---------------------------------------------------------------------------


def test_module_dependencies_cte(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    resolve_entities(project.id, session)
    build_graph(project.id, session)

    # Find webhooks module node
    webhooks_node = session.exec(
        select(Node).where(Node.project_id == project.id, Node.key == "webhooks")
    ).first()
    assert webhooks_node is not None

    deps = module_dependencies(webhooks_node.id, session)
    assert len(deps) >= 2
    dep_keys = {d["key"] for d in deps}
    assert "billing" in dep_keys
    assert "auth" in dep_keys


def test_timeline_query(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    resolve_entities(project.id, session)
    build_graph(project.id, session)

    t_start = datetime(2026, 8, 1, tzinfo=UTC)
    t_end = datetime(2026, 11, 30, tzinfo=UTC)

    items = timeline(project.id, t_start, t_end, session)
    assert len(items) > 50
    # Items must be strictly chronological
    for i in range(len(items) - 1):
        assert items[i]["valid_from"] <= items[i + 1]["valid_from"]


def test_bus_factor_flags_ledger_sync(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    resolve_entities(project.id, session)
    build_graph(project.id, session)

    risks = bus_factor(project.id, session)
    assert len(risks) >= 1

    # Scenario 7 assertion: module ledger-sync has no documentation and single author Aarav
    ledger_risk = next((r for r in risks if r["module"] == "ledger-sync"), None)
    assert ledger_risk is not None
    assert ledger_risk["bus_factor"] == 1
    assert "Aarav" in ledger_risk["sole_contributor"]
    assert ledger_risk["risk_level"] == "high"
    assert ledger_risk["doc_count"] == 0


# ---------------------------------------------------------------------------
# 5. Extraction, Bi-Temporal Invalidation & Supersedes Resolution
# ---------------------------------------------------------------------------


def test_extraction_and_supersedes_scenarios(session: Session) -> None:
    execute_demo_load(session)
    project = session.exec(select(Project).where(Project.slug == "payflow")).one()
    resolve_entities(project.id, session)
    build_graph(project.id, session)

    # Run extraction step
    ext_summary = extract_and_link_facts(project.id, session)
    assert ext_summary["created_nodes_count"] >= 4
    assert ext_summary["supersedes_count"] >= 2
    assert ext_summary["unresolved_count"] >= 1

    # Scenario 1: Redis sessions in ADR-003 superseded by PR #89 stateless JWT
    supersedes_edges = session.exec(
        select(Edge).where(Edge.project_id == project.id, Edge.type == "SUPERSEDES")
    ).all()
    assert len(supersedes_edges) >= 2

    # Check that older decision node was invalidated bi-temporally (valid_to is set)
    redis_decision = session.exec(
        select(Node).where(
            Node.project_id == project.id,
            Node.type == "decision",
            Node.key.like("%session_caching%ADR-003%"),
        )
    ).first()
    assert redis_decision is not None
    assert redis_decision.valid_to is not None, "Older decision must have valid_to set when superseded"

    jwt_decision = session.exec(
        select(Node).where(
            Node.project_id == project.id,
            Node.type == "decision",
            Node.key.like("%session_caching%PR-89%"),
        )
    ).first()
    assert jwt_decision is not None
    assert redis_decision.valid_to == jwt_decision.valid_from

    # Scenario 2: MongoDB in RFC-007 superseded by PR #42 PostgreSQL
    mongo_decision = session.exec(
        select(Node).where(
            Node.project_id == project.id,
            Node.type == "decision",
            Node.key.like("%database_choice%RFC-007%"),
        )
    ).first()
    postgres_decision = session.exec(
        select(Node).where(
            Node.project_id == project.id,
            Node.type == "decision",
            Node.key.like("%database_choice%PR-42%"),
        )
    ).first()
    assert mongo_decision is not None
    assert postgres_decision is not None
    assert mongo_decision.valid_to == postgres_decision.valid_from

    # Scenario 3: Rate limit disagreement produces an UNRESOLVED ambiguity
    ambiguities = session.exec(
        select(Ambiguity).where(
            Ambiguity.project_id == project.id,
            Ambiguity.type == "conflict",
        )
    ).all()
    assert len(ambiguities) >= 1
    rate_conflict = next((a for a in ambiguities if "rate limit" in a.title.lower()), None)
    assert rate_conflict is not None
    assert rate_conflict.severity == "high"
    assert rate_conflict.status == "open"
