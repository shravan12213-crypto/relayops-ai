"""GitHub REST API live ingestion loader."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx

from ..config import get_settings
from ..errors import AppError
from .base import RawEvent

logger = logging.getLogger("relayops.ingest.github")


class GitHubLiveLoader:
    """Live loader fetching commits, PRs, issues, and branches from GitHub API."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or get_settings().github_token
        self._etags: dict[str, str] = {}

    def _get_headers(self, url: str) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "RelayOps-Ingestion/0.1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if url in self._etags:
            headers["If-None-Match"] = self._etags[url]
        return headers

    def load(
        self,
        repo: str,
        max_items: int = 100,
        **kwargs: Any,
    ) -> Iterator[RawEvent]:
        """Load all artifacts from a GitHub repository ('owner/repo')."""
        if not repo or "/" not in repo:
            raise AppError(
                "BAD_REQUEST", f"Invalid GitHub repository format: '{repo}'. Expected 'owner/repo'."
            )

        owner, repo_name = repo.split("/", 1)
        client = httpx.Client(timeout=30.0)
        try:
            yield from self._load_branches(client, owner, repo_name)
            yield from self._load_commits(client, owner, repo_name, max_items)
            yield from self._load_pull_requests(client, owner, repo_name, max_items)
            yield from self._load_issues(client, owner, repo_name, max_items)
        finally:
            client.close()

    def _request(self, client: httpx.Client, url: str, params: dict[str, Any] | None = None) -> Any:
        headers = self._get_headers(url)
        try:
            resp = client.get(url, headers=headers, params=params)
        except httpx.RequestError as exc:
            logger.warning("GitHub request failed: %s", exc)
            return None

        # ETag 304 Not Modified
        if resp.status_code == 304:
            return None

        # Rate limiting check
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) <= 0:
            reset_ts = resp.headers.get("X-RateLimit-Reset", "0")
            msg = f"GitHub API rate limit exceeded. Resets at UTC timestamp {reset_ts}."
            logger.error(msg)
            raise AppError("RATE_LIMITED", msg, status_code=429)

        if resp.status_code in (401, 403):
            msg = f"GitHub authentication failure (status {resp.status_code}). Verify GITHUB_TOKEN."
            logger.warning(msg)
            raise AppError("FORBIDDEN", msg, status_code=403)

        if resp.status_code == 404:
            msg = f"Repository not found or access denied (status 404): {url}"
            logger.warning(msg)
            raise AppError("NOT_FOUND", msg, status_code=404)

        if resp.status_code >= 400:
            logger.warning("GitHub API returned error %s for %s", resp.status_code, url)
            return None

        etag = resp.headers.get("ETag")
        if etag:
            self._etags[url] = etag

        return resp.json()

    def _load_branches(self, client: httpx.Client, owner: str, repo: str) -> Iterator[RawEvent]:
        url = f"https://api.github.com/repos/{owner}/{repo}/branches"
        data = self._request(client, url)
        if not isinstance(data, list):
            return

        for b in data:
            name = b.get("name", "")
            commit_sha = b.get("commit", {}).get("sha", "")
            yield RawEvent(
                kind="branch",
                external_id=name,
                source_uri=f"https://github.com/{owner}/{repo}/tree/{name}",
                title=f"Branch {name}",
                body=f"Branch: {name}\nLast commit: {commit_sha}",
                author_alias="github",
                occurred_at=datetime.now(UTC),
                meta={"name": name, "last_commit_sha": commit_sha},
                acl_hint="internal",
            )

    def _load_commits(
        self, client: httpx.Client, owner: str, repo: str, max_items: int
    ) -> Iterator[RawEvent]:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        data = self._request(client, url, params={"per_page": min(max_items, 100)})
        if not isinstance(data, list):
            return

        for c in data[:max_items]:
            sha = c.get("sha", "")
            c_data = c.get("commit", {})
            author_data = c_data.get("author", {})
            msg = c_data.get("message", "")
            dt_str = author_data.get("date")
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")) if dt_str else datetime.now(UTC)
            except Exception:
                dt = datetime.now(UTC)

            first_line = msg.splitlines()[0] if msg else f"Commit {sha[:8]}"
            yield RawEvent(
                kind="commit",
                external_id=sha,
                source_uri=f"https://github.com/{owner}/{repo}/commit/{sha}",
                title=first_line,
                body=msg,
                author_alias=author_data.get("name") or author_data.get("email") or "github",
                occurred_at=dt,
                meta={"sha": sha, "author_email": author_data.get("email")},
                acl_hint="internal",
            )

    def _load_pull_requests(
        self, client: httpx.Client, owner: str, repo: str, max_items: int
    ) -> Iterator[RawEvent]:
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        data = self._request(client, url, params={"state": "all", "per_page": min(max_items, 100)})
        if not isinstance(data, list):
            return

        for pr in data[:max_items]:
            number = pr.get("number")
            title = pr.get("title", f"PR #{number}")
            body = pr.get("body") or ""
            dt_str = pr.get("merged_at") or pr.get("closed_at") or pr.get("created_at")
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")) if dt_str else datetime.now(UTC)
            except Exception:
                dt = datetime.now(UTC)

            yield RawEvent(
                kind="pull_request",
                external_id=str(number),
                source_uri=pr.get("html_url", f"https://github.com/{owner}/{repo}/pull/{number}"),
                title=f"PR #{number}: {title}",
                body=body,
                author_alias=pr.get("user", {}).get("login", "unknown"),
                occurred_at=dt,
                meta={"number": number, "state": pr.get("state")},
                acl_hint="internal",
            )

    def _load_issues(self, client: httpx.Client, owner: str, repo: str, max_items: int) -> Iterator[RawEvent]:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        data = self._request(client, url, params={"state": "all", "per_page": min(max_items, 100)})
        if not isinstance(data, list):
            return

        for issue in data[:max_items]:
            if "pull_request" in issue:
                continue
            number = issue.get("number")
            title = issue.get("title", f"Issue #{number}")
            body = issue.get("body") or ""
            dt_str = issue.get("created_at")
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")) if dt_str else datetime.now(UTC)
            except Exception:
                dt = datetime.now(UTC)

            yield RawEvent(
                kind="issue",
                external_id=f"GH-{number}",
                source_uri=issue.get("html_url", f"https://github.com/{owner}/{repo}/issues/{number}"),
                title=f"[GH-{number}] {title}",
                body=body,
                author_alias=issue.get("user", {}).get("login", "unknown"),
                occurred_at=dt,
                meta={"number": number, "state": issue.get("state")},
                acl_hint="internal",
            )
