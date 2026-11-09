"""JSON data loaders for commits, pull requests, branches, issues, and Slack threads."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from .base import RawEvent


def parse_datetime(val: str | datetime | None) -> datetime:
    if isinstance(val, datetime):
        return val.astimezone(UTC)
    if not val:
        return datetime.now(UTC)
    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
    return dt.astimezone(UTC)


class CommitsLoader:
    """Pure loader for commits.json."""

    def load(self, content: str | list[dict[str, Any]], **kwargs: Any) -> Iterator[RawEvent]:
        items = json.loads(content) if isinstance(content, str) else content
        for c in items:
            sha = str(c["sha"])
            msg = str(c.get("message", ""))
            files = list(c.get("files_changed", []))
            first_line = msg.splitlines()[0] if msg else f"Commit {sha[:8]}"
            body = msg
            if files:
                body += "\n\nFiles changed:\n" + "\n".join(f"- {f}" for f in files)

            yield RawEvent(
                kind="commit",
                external_id=sha,
                source_uri=f"https://github.com/payflow/commit/{sha}",
                title=first_line,
                body=body,
                author_alias=str(c.get("author") or c.get("author_email") or "unknown"),
                occurred_at=parse_datetime(c.get("date")),
                meta={
                    "sha": sha,
                    "files_changed": files,
                    "pr_num": c.get("pr_num"),
                    "author_email": c.get("author_email"),
                },
                acl_hint="internal",
            )


class PullRequestsLoader:
    """Pure loader for pull_requests.json."""

    def load(self, content: str | list[dict[str, Any]], **kwargs: Any) -> Iterator[RawEvent]:
        items = json.loads(content) if isinstance(content, str) else content
        for pr in items:
            number = int(pr["number"])
            title = str(pr.get("title", f"PR #{number}"))
            body = str(pr.get("body", ""))
            comments = pr.get("review_comments", [])
            if comments:
                body += "\n\n## Review Comments\n"
                for rc in comments:
                    body += f"\n- **{rc['author']}** ({rc.get('date', '')}): {rc['body']}"

            dt_val = pr.get("merged_at") or pr.get("closed_at") or pr.get("created_at")
            yield RawEvent(
                kind="pull_request",
                external_id=str(number),
                source_uri=f"https://github.com/payflow/pull/{number}",
                title=f"PR #{number}: {title}",
                body=body,
                author_alias=str(pr.get("author", "unknown")),
                occurred_at=parse_datetime(dt_val),
                meta={
                    "number": number,
                    "status": pr.get("status", "merged"),
                    "source_branch": pr.get("source_branch"),
                    "target_branch": pr.get("target_branch"),
                    "review_comments": comments,
                },
                acl_hint="internal",
            )


class BranchesLoader:
    """Pure loader for branches.json."""

    def load(self, content: str | list[dict[str, Any]], **kwargs: Any) -> Iterator[RawEvent]:
        items = json.loads(content) if isinstance(content, str) else content
        for b in items:
            name = str(b["name"])
            merged = bool(b.get("merged", False))
            ahead_by = int(b.get("ahead_by", 0))
            behind_by = int(b.get("behind_by", 0))
            last_sha = str(b.get("last_commit_sha", ""))

            body = (
                f"Branch: {name}\n"
                f"Author: {b.get('author', 'unknown')}\n"
                f"Merged to default: {merged}\n"
                f"Ahead by: {ahead_by} commits\n"
                f"Behind by: {behind_by} commits\n"
                f"Last commit: {last_sha}"
            )

            yield RawEvent(
                kind="branch",
                external_id=name,
                source_uri=f"https://github.com/payflow/tree/{name}",
                title=f"Branch {name}",
                body=body,
                author_alias=str(b.get("author", "unknown")),
                occurred_at=parse_datetime(b.get("updated_at")),
                meta={
                    "name": name,
                    "last_commit_sha": last_sha,
                    "merged": merged,
                    "ahead_by": ahead_by,
                    "behind_by": behind_by,
                },
                acl_hint="internal",
            )


class IssuesLoader:
    """Pure loader for issues.json."""

    def load(self, content: str | list[dict[str, Any]], **kwargs: Any) -> Iterator[RawEvent]:
        items = json.loads(content) if isinstance(content, str) else content
        for issue in items:
            key = str(issue["key"])
            title = str(issue.get("title", ""))
            desc = str(issue.get("description", ""))

            yield RawEvent(
                kind="issue",
                external_id=key,
                source_uri=f"https://jira.internal/browse/{key}",
                title=f"[{key}] {title}",
                body=desc,
                author_alias=str(issue.get("reporter", "unknown")),
                occurred_at=parse_datetime(issue.get("created_at") or issue.get("updated_at")),
                meta={
                    "key": key,
                    "status": issue.get("status"),
                    "assignee": issue.get("assignee"),
                    "blocked_by": list(issue.get("blocked_by", [])),
                    "labels": list(issue.get("labels", [])),
                },
                acl_hint="internal",
            )


class SlackLoader:
    """Pure loader for slack_*.json channels.

    Encodes one Slack thread as a single artifact with replies concatenated and
    per-message character offsets recorded in meta, enabling precise evidence citations.
    """

    def load(self, content: str | list[dict[str, Any]], **kwargs: Any) -> Iterator[RawEvent]:
        items = json.loads(content) if isinstance(content, str) else content
        for thread in items:
            thread_id = str(thread["thread_id"])
            channel = str(thread.get("channel", "general"))
            sensitivity = int(thread.get("sensitivity", 1))
            root = thread["root"]
            replies = thread.get("replies", [])

            body_parts: list[str] = []
            offsets: list[dict[str, Any]] = []
            current_pos = 0

            root_header = f"[{channel}] {root['user']} ({root.get('ts', '')}):\n"
            root_text = str(root.get("text", ""))
            root_block = root_header + root_text
            offsets.append(
                {
                    "message_id": root["message_id"],
                    "user": root["user"],
                    "user_email": root.get("user_email"),
                    "ts": root.get("ts"),
                    "char_start": current_pos,
                    "char_end": current_pos + len(root_block),
                }
            )
            body_parts.append(root_block)
            current_pos += len(root_block)

            for rep in replies:
                rep_header = f"\n\n---\n[{channel}] {rep['user']} ({rep.get('ts', '')}):\n"
                rep_text = str(rep.get("text", ""))
                rep_block = rep_header + rep_text
                offsets.append(
                    {
                        "message_id": rep["message_id"],
                        "user": rep["user"],
                        "user_email": rep.get("user_email"),
                        "ts": rep.get("ts"),
                        "char_start": current_pos,
                        "char_end": current_pos + len(rep_block),
                    }
                )
                body_parts.append(rep_block)
                current_pos += len(rep_block)

            full_body = "".join(body_parts)
            first_line = root_text.splitlines()[0][:60] if root_text else thread_id
            acl = "confidential" if sensitivity >= 2 or channel == "leads-private" else "internal"

            yield RawEvent(
                kind="chat_thread",
                external_id=thread_id,
                source_uri=f"https://payflow.slack.com/archives/{channel}/{thread_id}",
                title=f"#{channel}: {first_line}",
                body=full_body,
                author_alias=str(root.get("user", "unknown")),
                occurred_at=parse_datetime(root.get("ts")),
                meta={
                    "channel": channel,
                    "thread_id": thread_id,
                    "sensitivity": sensitivity,
                    "messages": offsets,
                    "reply_count": len(replies),
                },
                acl_hint=acl,
            )
