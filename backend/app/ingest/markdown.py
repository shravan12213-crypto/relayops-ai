"""Markdown and text document ingestion loader."""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .base import RawEvent


class MarkdownLoader:
    """Pure loader for .md and .txt files. Infers document kind from name and content."""

    def load(
        self,
        content: str | Path,
        filename: str | None = None,
        **kwargs: Any,
    ) -> Iterator[RawEvent]:
        file_path: Path | None = None
        if isinstance(content, Path):
            file_path = content
            text = content.read_text(encoding="utf-8")
            name = filename or content.name
        else:
            text = content
            name = filename or "document.md"

        kind = self._infer_kind(name, text)
        title = self._infer_title(name, text)
        author = self._infer_author(text)
        occurred_at = self._infer_date(text, file_path)

        # Canonical key: ADR-003, RFC-007, or the file basename
        external_id = name
        match_doc_code = re.search(r"((?:ADR|RFC)-\d+)", name, re.IGNORECASE)
        if match_doc_code:
            external_id = match_doc_code.group(1).upper()

        yield RawEvent(
            kind=kind,
            external_id=external_id,
            source_uri=f"file://docs/{name}",
            title=title,
            body=text,
            author_alias=author,
            occurred_at=occurred_at,
            meta={"filename": name, "inferred_kind": kind},
            acl_hint="internal",
        )

    def _infer_kind(self, name: str, text: str) -> str:
        lowered = f"{name} {text[:200]}".lower()
        if "adr-" in lowered or "adr:" in lowered or "rfc-" in lowered or "rfc:" in lowered:
            return "adr_doc"
        if "runbook" in lowered or "playbook" in lowered:
            return "runbook"
        if "meeting" in lowered or "minutes" in lowered or "sync" in lowered:
            return "meeting_note"
        return "adr_doc"

    def _infer_title(self, name: str, text: str) -> str:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
            if line.lower().startswith("title:"):
                return line.split(":", 1)[1].strip()
        stem = Path(name).stem.replace("-", " ").replace("_", " ")
        return stem.title()

    def _infer_author(self, text: str) -> str:
        match = re.search(r"(?:Author|Maintainer):\s*([^\n\r,]+)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "system"

    def _infer_date(self, text: str, file_path: Path | None) -> datetime:
        # 1. Match explicit ISO dates (Date: 2026-10-12, **Date**: 2026-10-12)
        match = re.search(r"(?:Date|Created|Updated)[*\s]*:\s*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        if match:
            try:
                return datetime.fromisoformat(f"{match.group(1)}T00:00:00+00:00")
            except ValueError:
                pass

        # 2. Match natural language dates like "Oct 12, 2026", "October 12, 2026", "August 11, 2026"
        month_pattern = (
            r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        )
        match_named = re.search(
            rf"\b({month_pattern}\s+\d{1,2},?\s+\d{4})\b",
            text,
            re.IGNORECASE,
        )
        if match_named:
            date_str = match_named.group(1).replace(",", "")
            for fmt in ("%B %d %Y", "%b %d %Y"):
                try:
                    return datetime.strptime(date_str, fmt).replace(tzinfo=UTC)
                except ValueError:
                    pass

        # 3. Match dates in filename, e.g. meeting-note-2026-10-14.md
        if file_path:
            match_fn = re.search(r"(\d{4}-\d{2}-\d{2})", file_path.name)
            if match_fn:
                try:
                    return datetime.fromisoformat(f"{match_fn.group(1)}T00:00:00+00:00")
                except ValueError:
                    pass

        if file_path and file_path.exists():
            return datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC)
        return datetime.now(UTC)
