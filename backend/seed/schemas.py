"""Pydantic validation schemas for the PayFlow synthetic seed dataset and ground truth."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UserSeed(BaseModel):
    id: str
    email: str
    name: str
    password: str
    role: str
    clearance: int
    is_active: bool = True
    aliases: list[str] = Field(default_factory=list)


class CommitSeed(BaseModel):
    sha: str
    author: str
    author_email: str
    date: str
    message: str
    files_changed: list[str]
    pr_num: int | None = None


class PRCommentSeed(BaseModel):
    author: str
    date: str
    body: str


class PullRequestSeed(BaseModel):
    number: int
    title: str
    author: str
    created_at: str
    closed_at: str | None = None
    merged_at: str | None = None
    status: str  # merged | open | closed
    body: str
    source_branch: str
    target_branch: str
    review_comments: list[PRCommentSeed] = Field(default_factory=list)


class BranchSeed(BaseModel):
    name: str
    last_commit_sha: str
    author: str
    updated_at: str
    merged: bool
    ahead_by: int
    behind_by: int


class IssueSeed(BaseModel):
    key: str  # PAY-101
    title: str
    description: str
    reporter: str
    assignee: str | None = None
    status: str  # open | in_progress | resolved | closed | blocked
    created_at: str
    updated_at: str
    blocked_by: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)


class SlackMessageSeed(BaseModel):
    message_id: str
    user: str
    user_email: str | None = None
    text: str
    ts: str


class SlackThreadSeed(BaseModel):
    thread_id: str
    channel: str
    sensitivity: int = 1
    root: SlackMessageSeed
    replies: list[SlackMessageSeed] = Field(default_factory=list)


class GroundTruthScenario(BaseModel):
    scenario_num: int
    title: str
    kind: str
    description: str
    expected_artifact_ids: list[str]
    details: dict[str, Any] = Field(default_factory=dict)


class PlantedSecret(BaseModel):
    kind: str  # api_key | aws_key | bearer_token | db_url | email | phone | salary
    raw: str
    location: str


class GroundTruth(BaseModel):
    project_slug: str
    project_name: str
    scenario_count: int
    scenarios: list[GroundTruthScenario]
    planted_secrets: list[PlantedSecret]
    expected_ambiguities_summary: dict[str, int]
