"""Handover package: claims review, version snapshots, dual sign-off, diffs,
role views, plan, copilot, receipts, and export generators.
"""

from app.handover.claims import (
    AmbiguityResolveInput,
    AmbiguityWaiveInput,
    ClaimCreateInput,
    ClaimPatchInput,
    create_human_claim,
    list_handover_ambiguities,
    list_handover_claims,
    patch_claim,
    resolve_ambiguity,
    waive_ambiguity,
)
from app.handover.copilot import ask_copilot
from app.handover.export import export_handover
from app.handover.plan import (
    PlanItemCreateInput,
    PlanItemUpdateInput,
    create_plan_item,
    get_plan,
    update_plan_item,
)
from app.handover.receipts import (
    ReceiptInput,
    acknowledge_section_receipt,
    get_receipts_progress,
)
from app.handover.signoff import (
    compute_signoff_hmac,
    execute_signoff,
    invalidate_handover_signoffs,
    verify_handover,
)
from app.handover.versions import (
    canonical_json,
    compute_version_hash,
    compute_word_diff,
    create_snapshot,
    diff_versions,
)
from app.handover.views import (
    build_handover_view,
    deliver_handover,
)

__all__ = [
    "AmbiguityResolveInput",
    "AmbiguityWaiveInput",
    "ClaimCreateInput",
    "ClaimPatchInput",
    "PlanItemCreateInput",
    "PlanItemUpdateInput",
    "ReceiptInput",
    "acknowledge_section_receipt",
    "ask_copilot",
    "build_handover_view",
    "canonical_json",
    "compute_signoff_hmac",
    "compute_version_hash",
    "compute_word_diff",
    "create_human_claim",
    "create_plan_item",
    "create_snapshot",
    "deliver_handover",
    "diff_versions",
    "execute_signoff",
    "export_handover",
    "get_plan",
    "get_receipts_progress",
    "invalidate_handover_signoffs",
    "list_handover_ambiguities",
    "list_handover_claims",
    "patch_claim",
    "resolve_ambiguity",
    "update_plan_item",
    "verify_handover",
    "waive_ambiguity",
]
