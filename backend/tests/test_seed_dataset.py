"""Tests for P04: Synthetic seed dataset, ground truth scenarios, schema validation, and reproducibility."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from seed.schemas import (
    BranchSeed,
    CommitSeed,
    GroundTruth,
    IssueSeed,
    PullRequestSeed,
    SlackThreadSeed,
    UserSeed,
)

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
DATA_DIR = SEED_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"


def test_seed_files_exist() -> None:
    expected_files = [
        DATA_DIR / "users.json",
        DATA_DIR / "branches.json",
        DATA_DIR / "commits.json",
        DATA_DIR / "pull_requests.json",
        DATA_DIR / "issues.json",
        DATA_DIR / "slack_backend-dev.json",
        DATA_DIR / "slack_leads-private.json",
        DATA_DIR / "slack_incidents.json",
        DOCS_DIR / "ADR-003-caching.md",
        DOCS_DIR / "RFC-007-database-choice.md",
        DOCS_DIR / "runbook-webhooks.md",
        DOCS_DIR / "onboarding.md",
        DOCS_DIR / "meeting-note-2026-10-14.md",
        SEED_DIR / "ground_truth.json",
    ]
    for file_path in expected_files:
        assert file_path.exists(), f"Missing required seed file: {file_path}"
        assert file_path.stat().st_size > 0, f"File is empty: {file_path}"


def test_schema_validations() -> None:
    # 1. users.json
    users_raw = json.loads((DATA_DIR / "users.json").read_text(encoding="utf-8"))
    users = TypeAdapter(list[UserSeed]).validate_python(users_raw)
    assert len(users) == 5
    roles = {u.role for u in users}
    assert roles == {"outgoing", "lead", "successor", "auditor", "contractor"}

    # 2. branches.json
    branches_raw = json.loads((DATA_DIR / "branches.json").read_text(encoding="utf-8"))
    branches = TypeAdapter(list[BranchSeed]).validate_python(branches_raw)
    assert len(branches) >= 5
    branch_names = {b.name for b in branches}
    assert "feature/webhook-retry-v2" in branch_names
    assert "hotfix/idempotency-keys" in branch_names

    # 3. commits.json
    commits_raw = json.loads((DATA_DIR / "commits.json").read_text(encoding="utf-8"))
    commits = TypeAdapter(list[CommitSeed]).validate_python(commits_raw)
    assert len(commits) >= 80

    # 4. pull_requests.json
    prs_raw = json.loads((DATA_DIR / "pull_requests.json").read_text(encoding="utf-8"))
    prs = TypeAdapter(list[PullRequestSeed]).validate_python(prs_raw)
    assert len(prs) >= 20
    pr_nums = {p.number for p in prs}
    assert 42 in pr_nums
    assert 65 in pr_nums
    assert 89 in pr_nums
    assert 92 in pr_nums
    assert 94 in pr_nums

    # 5. issues.json
    issues_raw = json.loads((DATA_DIR / "issues.json").read_text(encoding="utf-8"))
    issues = TypeAdapter(list[IssueSeed]).validate_python(issues_raw)
    assert len(issues) >= 20
    issue_keys = {i.key for i in issues}
    assert "PAY-142" in issue_keys

    # 6. slack channels
    for chan_file in ["slack_backend-dev.json", "slack_leads-private.json", "slack_incidents.json"]:
        threads_raw = json.loads((DATA_DIR / chan_file).read_text(encoding="utf-8"))
        threads = TypeAdapter(list[SlackThreadSeed]).validate_python(threads_raw)
        assert len(threads) > 0

    # 7. ground_truth.json
    gt_raw = json.loads((SEED_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    gt = GroundTruth.model_validate(gt_raw)
    assert gt.project_slug == "payflow"
    assert gt.scenario_count == 10
    assert len(gt.scenarios) == 10


def test_all_10_scenarios_present_in_ground_truth() -> None:
    gt_raw = json.loads((SEED_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    gt = GroundTruth.model_validate(gt_raw)

    scenarios_by_num = {s.scenario_num: s for s in gt.scenarios}
    assert len(scenarios_by_num) == 10

    # Verify each scenario
    s1 = scenarios_by_num[1]
    assert s1.kind == "SUPERSEDES"
    assert "ADR-003" in s1.expected_artifact_ids
    assert "PR-89" in s1.expected_artifact_ids

    s2 = scenarios_by_num[2]
    assert s2.kind == "SUPERSEDES"
    assert "RFC-007" in s2.expected_artifact_ids
    assert "PR-42" in s2.expected_artifact_ids

    s3 = scenarios_by_num[3]
    assert s3.kind == "CONFLICT"
    assert "msg_rate_100" in s3.expected_artifact_ids
    assert "msg_rate_500" in s3.expected_artifact_ids

    s4 = scenarios_by_num[4]
    assert s4.kind == "CONTRADICTION"
    assert "runbook-webhooks.md" in s4.expected_artifact_ids
    assert "PR-65" in s4.expected_artifact_ids

    s5 = scenarios_by_num[5]
    assert s5.kind == "AMBIGUITY"
    assert "feature/webhook-retry-v2" in s5.expected_artifact_ids
    assert "hotfix/idempotency-keys" in s5.expected_artifact_ids

    s6 = scenarios_by_num[6]
    assert s6.kind == "BLOCKER"
    assert "PAY-142" in s6.expected_artifact_ids
    assert "msg_leads_vendor_01" in s6.expected_artifact_ids

    s7 = scenarios_by_num[7]
    assert s7.kind == "AMBIGUITY"
    assert len(s7.expected_artifact_ids) >= 2

    s8 = scenarios_by_num[8]
    assert s8.kind == "SECRET_REDACTION"
    assert len(gt.planted_secrets) >= 7

    s9 = scenarios_by_num[9]
    assert s9.kind == "AMBIGUITY"
    assert "runbook-webhooks.md" in s9.expected_artifact_ids

    s10 = scenarios_by_num[10]
    assert s10.kind == "AMBIGUITY"
    assert "msg_unanswered_01" in s10.expected_artifact_ids


def test_ground_truth_references_only_existing_artifacts() -> None:
    """Every artifact referenced in ground_truth.json must exist in the generated dataset."""
    commits = json.loads((DATA_DIR / "commits.json").read_text(encoding="utf-8"))
    prs = json.loads((DATA_DIR / "pull_requests.json").read_text(encoding="utf-8"))
    branches = json.loads((DATA_DIR / "branches.json").read_text(encoding="utf-8"))
    issues = json.loads((DATA_DIR / "issues.json").read_text(encoding="utf-8"))
    bk_threads = json.loads((DATA_DIR / "slack_backend-dev.json").read_text(encoding="utf-8"))
    leads_threads = json.loads((DATA_DIR / "slack_leads-private.json").read_text(encoding="utf-8"))
    inc_threads = json.loads((DATA_DIR / "slack_incidents.json").read_text(encoding="utf-8"))

    commit_shas = {c["sha"] for c in commits}
    pr_identifiers = {f"PR-{p['number']}" for p in prs} | {str(p["number"]) for p in prs}
    branch_names = {b["name"] for b in branches}
    issue_keys = {i["key"] for i in issues}

    all_slack_msg_ids: set[str] = set()
    for threads in [bk_threads, leads_threads, inc_threads]:
        for t in threads:
            all_slack_msg_ids.add(t["root"]["message_id"])
            for r in t.get("replies", []):
                all_slack_msg_ids.add(r["message_id"])

    doc_names = {f.name for f in DOCS_DIR.glob("*.md")}
    doc_keys = {"ADR-003", "RFC-007"} | doc_names

    all_valid_identifiers = (
        commit_shas | pr_identifiers | branch_names | issue_keys | all_slack_msg_ids | doc_keys
    )

    gt_raw = json.loads((SEED_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    gt = GroundTruth.model_validate(gt_raw)

    for scenario in gt.scenarios:
        for art_id in scenario.expected_artifact_ids:
            assert (
                art_id in all_valid_identifiers
            ), f"Scenario {scenario.scenario_num} references non-existent artifact: '{art_id}'"
