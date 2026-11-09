"""Ingestion base classes, protocol, and raw event data structures."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass
class RawEvent:
    """Standard normalized event yielded by all ingestion loaders."""

    kind: str  # commit | pull_request | issue | chat_thread | adr_doc | meeting_note | runbook | branch
    external_id: str
    source_uri: str
    title: str
    body: str
    author_alias: str
    occurred_at: datetime
    meta: dict[str, Any] = field(default_factory=dict)
    acl_hint: str | None = None  # public | internal | confidential | restricted


class Loader(Protocol):
    """Protocol for all data source loaders. Loaders are pure (no database writes)."""

    def load(self, content: Any, **kwargs: Any) -> Iterator[RawEvent]: ...
