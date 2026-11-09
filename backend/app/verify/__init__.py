"""Verification: citation validation, conflict detection, ambiguity ledger and scorecard."""

from .ambiguity import (
    detect_all_ambiguities,
    detect_low_evidence,
    detect_missing_docs,
    detect_orphan_branches,
    detect_stale_config,
    detect_unclosed_threads,
    detect_undocumented_modules,
)
from .citations import (
    bind_and_validate,
    compute_deep_link,
    find_best_span,
    validate_claims_batch,
)
from .conflicts import (
    ConflictResult,
    check_deterministic_conflict,
    detect_and_resolve_conflicts,
    evaluate_pair_with_llm,
    infer_subject_key,
)
from .scorecard import (
    ClaimScore,
    ScorecardData,
    compute_epistemic_confidence,
    generate_scorecard,
)

__all__ = [
    "ClaimScore",
    "ConflictResult",
    "ScorecardData",
    "bind_and_validate",
    "check_deterministic_conflict",
    "compute_deep_link",
    "compute_epistemic_confidence",
    "detect_all_ambiguities",
    "detect_and_resolve_conflicts",
    "detect_low_evidence",
    "detect_missing_docs",
    "detect_orphan_branches",
    "detect_stale_config",
    "detect_unclosed_threads",
    "detect_undocumented_modules",
    "evaluate_pair_with_llm",
    "find_best_span",
    "generate_scorecard",
    "infer_subject_key",
    "validate_claims_batch",
]
