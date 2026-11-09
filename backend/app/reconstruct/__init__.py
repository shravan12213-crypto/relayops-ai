"""Reconstruction: entities, temporal graph, authority resolution and claim extraction."""

from __future__ import annotations

from app.reconstruct.authority import (
    ResolutionResult,
    ResolutionStatus,
    authority_for,
    resolve,
)
from app.reconstruct.entities import (
    match_confidence,
    resolve_entities,
    resolve_modules_and_services,
    resolve_people_entities,
)
from app.reconstruct.extract import (
    ExtractedClaim,
    ExtractedFacts,
    extract_and_link_facts,
    extract_claims_for_topic,
)
from app.reconstruct.graph import (
    build_graph,
    bus_factor,
    module_dependencies,
    timeline,
)

__all__ = [
    "ExtractedClaim",
    "ExtractedFacts",
    "ResolutionResult",
    "ResolutionStatus",
    "authority_for",
    "build_graph",
    "bus_factor",
    "extract_and_link_facts",
    "extract_claims_for_topic",
    "match_confidence",
    "module_dependencies",
    "resolve",
    "resolve_entities",
    "resolve_modules_and_services",
    "resolve_people_entities",
    "timeline",
]
