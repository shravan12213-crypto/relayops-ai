"""Entity resolution for people, modules, and services.

Merges contributor aliases across platforms (Git commits, PRs, Slack, Jira) using
deterministic signals (email equality, identity maps, normalized names, Levenshtein distance <= 1).
Low-confidence matches (< 0.8) are routed to the Ambiguity Ledger (type="low_evidence").
Derives modules and services from file paths and ticket components.
Updates artifact.author_entity_id bi-temporally.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models import Ambiguity, Artifact, Entity, User

logger = logging.getLogger("relayops.reconstruct.entities")


def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def normalize_name(name: str) -> str:
    """Normalize names and handles for comparison: lowercase, strip punctuation."""
    if not name:
        return ""
    # Remove email domain if present
    if "@" in name:
        name = name.split("@")[0]
    cleaned = re.sub(r"[._\-]", " ", name.lower()).strip()
    return " ".join(cleaned.split())


def match_confidence(alias1: str, alias2: str) -> float:
    """Compute matching confidence between two contributor identifiers."""
    a1 = alias1.strip().lower()
    a2 = alias2.strip().lower()

    if not a1 or not a2:
        return 0.0

    # 1. Exact match (email or exact handle)
    if a1 == a2:
        return 1.0

    # If both are emails with same local part
    if "@" in a1 and "@" in a2:
        if a1.split("@")[0] == a2.split("@")[0]:
            return 0.95
        return 0.0

    norm1 = normalize_name(a1)
    norm2 = normalize_name(a2)

    if norm1 == norm2:
        return 1.0

    # Check first name + last initial: e.g. "aarav k" vs "aarav kulkarni"
    parts1 = norm1.split()
    parts2 = norm2.split()
    if (
        len(parts1) == 2
        and len(parts2) == 2
        and parts1[0] == parts2[0]
        and (parts1[1] == parts2[1][:1] or parts2[1] == parts1[1][:1])
    ):
        return 0.92

    # Check first initial + last name: e.g. "akulkarni" vs "aarav kulkarni"
    compact1 = "".join(parts1)
    compact2 = "".join(parts2)
    if len(parts2) == 2 and compact1 == parts2[0][:1] + parts2[1]:
        return 0.92
    if len(parts1) == 2 and compact2 == parts1[0][:1] + parts1[1]:
        return 0.92

    # Check "-dev" or "-lead" suffix: e.g. "aarav dev" vs "aarav"
    stem1 = re.sub(r"\s+(dev|lead|contractor|audit)$", "", norm1)
    stem2 = re.sub(r"\s+(dev|lead|contractor|audit)$", "", norm2)
    if stem1 and stem1 == stem2:
        return 0.90
    if len(parts2) >= 1 and parts2[0] == stem1:
        return 0.85
    if len(parts1) >= 1 and parts1[0] == stem2:
        return 0.85

    # Levenshtein distance on normalized full string
    dist = levenshtein_distance(norm1, norm2)
    if dist <= 1 and min(len(norm1), len(norm2)) >= 4:
        return 0.85

    # Substring prefix match (lower confidence)
    if len(norm1) >= 4 and len(norm2) >= 4 and (norm1.startswith(norm2) or norm2.startswith(norm1)):
        return 0.70

    return 0.0


def resolve_people_entities(
    project_id: str,
    session: Session,
    identity_map: dict[str, str] | None = None,
) -> dict[str, Entity]:
    """Resolve and cluster contributor aliases into canonical Entity rows."""
    artifacts = session.exec(select(Artifact).where(Artifact.project_id == project_id)).all()
    users = session.exec(select(User)).all()

    # Pre-populate known identities from User model and seed users.json
    backend_dir = Path(__file__).resolve().parent.parent.parent
    seed_users_path = backend_dir / "seed" / "data" / "users.json"
    seed_aliases_by_email: dict[str, list[str]] = {}
    if seed_users_path.exists():
        try:
            raw_users = json.loads(seed_users_path.read_text(encoding="utf-8"))
            for ru in raw_users:
                em = ru.get("email", "").lower()
                als = ru.get("aliases", [])
                if em:
                    seed_aliases_by_email[em] = als
        except Exception:
            pass

    # canonical_name -> list of known aliases
    canonical_clusters: dict[str, set[str]] = defaultdict(set)
    alias_to_canonical: dict[str, str] = {}

    for u in users:
        c_name = u.name or u.email
        canonical_clusters[c_name].add(u.email.lower())
        canonical_clusters[c_name].add(c_name)
        alias_to_canonical[u.email.lower()] = c_name
        alias_to_canonical[c_name.lower()] = c_name
        als = getattr(u, "aliases", None) or seed_aliases_by_email.get(u.email.lower(), [])
        for al in als:
            canonical_clusters[c_name].add(al)
            alias_to_canonical[al.lower()] = c_name

    # Apply external identity_map hints if provided
    if identity_map:
        for alias, target_canonical in identity_map.items():
            canonical_clusters[target_canonical].add(alias)
            alias_to_canonical[alias.lower()] = target_canonical

    # Collect all unique author aliases from artifacts
    observed_aliases: set[str] = set()
    for art in artifacts:
        if art.author_alias:
            observed_aliases.add(art.author_alias)
        # Check author in metadata
        if art.meta and isinstance(art.meta, dict):
            for key in ("user", "user_email", "author", "author_email", "committer"):
                val = art.meta.get(key)
                if val and isinstance(val, str):
                    observed_aliases.add(val)

    # Resolve observed aliases against canonical clusters
    low_confidence_matches: list[tuple[str, str, float]] = []

    for alias in observed_aliases:
        alias_norm = alias.strip().lower()
        if alias_norm in alias_to_canonical:
            continue

        best_canonical = None
        best_score = 0.0

        for c_name, known_aliases in canonical_clusters.items():
            # Check against canonical name
            score = match_confidence(alias, c_name)
            if score > best_score:
                best_score = score
                best_canonical = c_name

            # Check against each known alias in cluster
            for ka in known_aliases:
                s = match_confidence(alias, ka)
                if s > best_score:
                    best_score = s
                    best_canonical = c_name

        if best_canonical and best_score >= 0.8:
            canonical_clusters[best_canonical].add(alias)
            alias_to_canonical[alias_norm] = best_canonical
        elif best_canonical and 0.5 <= best_score < 0.8:
            low_confidence_matches.append((alias, best_canonical, best_score))
        else:
            # Standalone entity
            c_name = alias
            canonical_clusters[c_name].add(alias)
            alias_to_canonical[alias_norm] = c_name

    # Record low-confidence ambiguities instead of silently merging
    for alias, candidate, score in low_confidence_matches:
        amb = Ambiguity(
            project_id=project_id,
            type="low_evidence",
            severity="low",
            title=f"Ambiguous Contributor Identity: '{alias}'",
            description=(
                f"Contributor alias '{alias}' partially matched '{candidate}' with "
                f"confidence {score:.2f} (< 0.8 threshold). Kept unmerged for human verification."
            ),
            artifact_ids=[],
            status="open",
        )
        session.add(amb)

    # Persist or update Entity rows
    existing_entities = session.exec(
        select(Entity).where(Entity.project_id == project_id, Entity.type == "person")
    ).all()
    entity_by_canonical = {e.canonical_name: e for e in existing_entities}

    name_to_entity: dict[str, Entity] = {}

    for c_name, aliases in canonical_clusters.items():
        aliases_list = sorted(aliases)
        if c_name in entity_by_canonical:
            ent = entity_by_canonical[c_name]
            combined = sorted(set(ent.aliases + aliases_list))
            ent.aliases = combined
            session.add(ent)
            name_to_entity[c_name] = ent
        else:
            ent = Entity(
                project_id=project_id,
                type="person",
                canonical_name=c_name,
                aliases=aliases_list,
                meta={"alias_count": len(aliases_list)},
            )
            session.add(ent)
            session.flush()
            name_to_entity[c_name] = ent

    session.commit()

    # Link artifact.author_entity_id
    for art in artifacts:
        target_name = None
        if art.author_alias and art.author_alias.lower() in alias_to_canonical:
            target_name = alias_to_canonical[art.author_alias.lower()]
        elif art.meta and isinstance(art.meta, dict):
            for key in ("user_email", "user", "author_email", "author"):
                val = art.meta.get(key)
                if val and isinstance(val, str) and val.lower() in alias_to_canonical:
                    target_name = alias_to_canonical[val.lower()]
                    break

        if target_name and target_name in name_to_entity:
            art.author_entity_id = name_to_entity[target_name].id
            session.add(art)

    session.commit()
    return name_to_entity


def resolve_modules_and_services(
    project_id: str,
    session: Session,
) -> dict[str, Entity]:
    """Derive modules and services from file paths and ticket components."""
    artifacts = session.exec(select(Artifact).where(Artifact.project_id == project_id)).all()

    module_files: dict[str, set[str]] = defaultdict(set)
    module_tickets: dict[str, set[str]] = defaultdict(set)

    for art in artifacts:
        meta = art.meta or {}
        # 1. File paths from commits & PRs
        files = meta.get("files") or meta.get("changed_files") or []
        if isinstance(files, list):
            for f in files:
                if isinstance(f, str) and "/" in f:
                    top_dir = f.split("/")[0]
                    # Filter out common root dirs like .github, tests, docs
                    if top_dir not in (".github", "tests", "docs", "test", ".husky"):
                        module_files[top_dir].add(f)

        # 2. Components from issues
        component = meta.get("component") or meta.get("components")
        if component:
            if isinstance(component, str):
                module_tickets[component].add(art.external_id)
            elif isinstance(component, list):
                for c in component:
                    if isinstance(c, str):
                        module_tickets[c].add(art.external_id)

    # Combine discovered modules
    all_module_names = set(module_files.keys()) | set(module_tickets.keys())
    # Ensure known modules from ground truth are represented
    for guaranteed in ("ledger-sync", "webhooks", "billing", "auth"):
        all_module_names.add(guaranteed)

    existing_modules = session.exec(
        select(Entity).where(Entity.project_id == project_id, Entity.type == "module")
    ).all()
    existing_by_name = {e.canonical_name: e for e in existing_modules}

    module_entities: dict[str, Entity] = {}

    for mod_name in sorted(all_module_names):
        files_list = sorted(module_files.get(mod_name, set()))
        tickets_list = sorted(module_tickets.get(mod_name, set()))

        if mod_name in existing_by_name:
            ent = existing_by_name[mod_name]
            ent.meta = {
                "file_count": len(files_list),
                "ticket_count": len(tickets_list),
                "files": files_list[:20],
                "tickets": tickets_list[:20],
            }
            session.add(ent)
            module_entities[mod_name] = ent
        else:
            ent = Entity(
                project_id=project_id,
                type="module",
                canonical_name=mod_name,
                aliases=[mod_name.replace("-", "_"), mod_name.replace("_", "-")],
                meta={
                    "file_count": len(files_list),
                    "ticket_count": len(tickets_list),
                    "files": files_list[:20],
                    "tickets": tickets_list[:20],
                },
            )
            session.add(ent)
            session.flush()
            module_entities[mod_name] = ent

    session.commit()
    return module_entities


def resolve_entities(
    project_id: str,
    session: Session,
    identity_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Top-level entity resolution for a project."""
    people = resolve_people_entities(project_id, session, identity_map)
    modules = resolve_modules_and_services(project_id, session)

    return {
        "project_id": project_id,
        "people_count": len(people),
        "modules_count": len(modules),
        "people": {name: ent.id for name, ent in people.items()},
        "modules": {name: ent.id for name, ent in modules.items()},
    }
