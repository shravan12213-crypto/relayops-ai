"""Secrets and PII redaction engine.

Standalone, dependency-free module enforcing pre-storage and pre-inference scrubbing.
Detects API keys, cloud credentials, tokens, private keys, connection URLs,
environment secrets, high-entropy tokens, emails, phone numbers, and compensation.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class RedactionEventInfo:
    rule: str
    count: int
    span_count: int
    sample_masked: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "count": self.count,
            "span_count": self.span_count,
            "sample_masked": self.sample_masked,
        }


@dataclass
class RedactionResult:
    text: str
    events: list[RedactionEventInfo]


def shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy for a string: H = -sum(p * log2(p))."""
    if not s:
        return 0.0
    counts = Counter(s)
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


# ---------------------------------------------------------------------------
# Individual Named Redaction Rules
# ---------------------------------------------------------------------------


def rule_private_key(text: str) -> tuple[str, list[str]]:
    pattern = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")
    matches = pattern.findall(text)
    if not matches:
        return text, []
    redacted = pattern.sub("[REDACTED:PRIVATE_KEY]", text)
    return redacted, matches


def rule_aws_key(text: str) -> tuple[str, list[str]]:
    pattern = re.compile(r"(?<![A-Z0-9])(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}(?![A-Z0-9])")
    matches = [m.group(0) for m in pattern.finditer(text)]
    if not matches:
        return text, []
    redacted = pattern.sub("[REDACTED:AWS_KEY]", text)
    return redacted, matches


def rule_api_key(text: str) -> tuple[str, list[str]]:
    pattern = re.compile(r"(?<![a-zA-Z0-9_])sk_(?:live|test)_[0-9a-zA-Z_]{16,}(?![a-zA-Z0-9_])")
    matches = pattern.findall(text)
    if not matches:
        return text, []
    redacted = pattern.sub("[REDACTED:API_KEY]", text)
    return redacted, matches


def rule_github_token(text: str) -> tuple[str, list[str]]:
    pattern = re.compile(
        r"(?<![a-zA-Z0-9_])(?:gh[pousr]_[0-9a-zA-Z]{30,}|github_pat_[0-9a-zA-Z_]{22,})(?![a-zA-Z0-9_])"
    )
    matches = pattern.findall(text)
    if not matches:
        return text, []
    redacted = pattern.sub("[REDACTED:GITHUB_TOKEN]", text)
    return redacted, matches


def rule_slack_token(text: str) -> tuple[str, list[str]]:
    pattern = re.compile(r"(?<![a-zA-Z0-9_])xox[baprs]-[0-9a-zA-Z-]{10,}(?![a-zA-Z0-9_])")
    matches = pattern.findall(text)
    if not matches:
        return text, []
    redacted = pattern.sub("[REDACTED:SLACK_TOKEN]", text)
    return redacted, matches


def rule_jwt(text: str) -> tuple[str, list[str]]:
    pattern = re.compile(
        r"(?<![a-zA-Z0-9_.-])eyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{2,}\.[a-zA-Z0-9_-]{6,}(?![a-zA-Z0-9_.-])"
    )
    matches = pattern.findall(text)
    if not matches:
        return text, []
    redacted = pattern.sub("[REDACTED:JWT]", text)
    return redacted, matches


def rule_bearer_token(text: str) -> tuple[str, list[str]]:
    pattern = re.compile(r"(?i)\bBearer\s+(?!\[REDACTED)[a-zA-Z0-9._~+/-]{15,}[a-zA-Z0-9_~+/-]")
    matches = pattern.findall(text)
    if not matches:
        return text, []
    redacted = pattern.sub("Bearer [REDACTED:TOKEN]", text)
    return redacted, matches


def rule_db_url(text: str) -> tuple[str, list[str]]:
    pattern = re.compile(
        r"\b(postgres|postgresql|mysql|mongodb|redis|amqp|mssql)://([^:\s/@]+):(?!(?:\[REDACTED))([^@\s/]+)@([^\s/]+)(/[^\s]*)?"
    )
    matches = [m.group(0) for m in pattern.finditer(text)]
    if not matches:
        return text, []

    def repl(m: re.Match[str]) -> str:
        scheme = m.group(1)
        user = m.group(2)
        host = m.group(4)
        path = m.group(5) or ""
        return f"{scheme}://{user}:[REDACTED:PASSWORD]@{host}{path}"

    redacted = pattern.sub(repl, text)
    return redacted, matches


def rule_env_var(text: str) -> tuple[str, list[str]]:
    pattern = re.compile(
        r"(?m)^(\s*(?:export\s+)?)([A-Za-z0-9_]*(?:SECRET|TOKEN|PASSWORD|KEY|AUTH|CREDENTIAL)[A-Za-z0-9_]*)\s*=\s*(['\"]?)(?!(?:\[REDACTED:))([^\r\n'\"]{6,})\3"
    )
    matches = [m.group(0) for m in pattern.finditer(text)]
    if not matches:
        return text, []

    def repl(m: re.Match[str]) -> str:
        prefix = m.group(1)
        key = m.group(2)
        quote = m.group(3)
        return f"{prefix}{key}={quote}[REDACTED:SECRET]{quote}"

    redacted = pattern.sub(repl, text)
    return redacted, matches


def rule_ip_creds(text: str) -> tuple[str, list[str]]:
    pattern = re.compile(
        r"\b(https?://)([^:\s/@]+):(?!(?:\[REDACTED))([^\s/]+)@((?:\d{1,3}\.){3}\d{1,3}(?::\d+)?(?:/[^\s]*)?)"
    )
    matches = [m.group(0) for m in pattern.finditer(text)]
    if not matches:
        return text, []

    def repl(m: re.Match[str]) -> str:
        scheme = m.group(1)
        user = m.group(2)
        target = m.group(4)
        return f"{scheme}{user}:[REDACTED:PASSWORD]@{target}"

    redacted = pattern.sub(repl, text)
    return redacted, matches


def rule_salary(text: str) -> tuple[str, list[str]]:
    # Case A: context word preceding currency & amount
    pattern_a = re.compile(
        r"(?i)\b(?:salary|compensation|comp|rate|bonus|raise|ctc|annualized|package|pay)\b[^$\d\r\n]{0,50}(?:([$€£]|USD|EUR|GBP)\s*([\d,]+(?:\.\d{2})?[kKmM]?)|([\d,]+(?:\.\d{2})?[kKmM]?)\s*([$€£]|USD|EUR|GBP))"
    )
    # Case B: currency & amount preceding context word
    pattern_b = re.compile(
        r"(?i)(?:([$€£]|USD|EUR|GBP)\s*([\d,]+(?:\.\d{2})?[kKmM]?)|([\d,]+(?:\.\d{2})?[kKmM]?)\s*([$€£]|USD|EUR|GBP))\s*(?:salary|compensation|comp|rate|bonus|raise|ctc|annualized|\bper\s+year\b|\bannually\b|package|pay)"
    )
    # Case C: isolated currency amount (standalone text or entire line)
    pattern_c = re.compile(
        r"(?m)^\s*(?:([$€£]|USD|EUR|GBP)\s*([\d,]+(?:\.\d{2})?[kKmM]?)|([\d,]+(?:\.\d{2})?[kKmM]?)\s*([$€£]|USD|EUR|GBP))\s*$"
    )

    matches: list[str] = []

    def repl_a(m: re.Match[str]) -> str:
        full = m.group(0)
        curr = m.group(1) or m.group(4) or "$"
        num = m.group(2) or m.group(3) or ""
        matches.append(f"{curr}{num}")
        idx_num = full.find(num)
        idx_curr = full.find(curr)
        start_idx = min(idx_num, idx_curr) if (idx_num != -1 and idx_curr != -1) else max(idx_num, idx_curr)
        return full[:start_idx] + "[REDACTED:COMPENSATION]"

    def repl_b(m: re.Match[str]) -> str:
        full = m.group(0)
        curr = m.group(1) or m.group(4) or "$"
        num = m.group(2) or m.group(3) or ""
        matches.append(f"{curr}{num}")
        idx_num = full.find(num)
        idx_curr = full.find(curr)
        end_idx = max(idx_num + len(num), idx_curr + len(curr))
        tail = full[end_idx:]
        return "[REDACTED:COMPENSATION]" + tail

    def repl_c(m: re.Match[str]) -> str:
        curr = m.group(1) or m.group(4) or "$"
        num = m.group(2) or m.group(3) or ""
        matches.append(f"{curr}{num}")
        return "[REDACTED:COMPENSATION]"

    step1 = pattern_a.sub(repl_a, text)
    step2 = pattern_b.sub(repl_b, step1)
    step3 = pattern_c.sub(repl_c, step2)
    return step3, matches


def rule_phone(text: str) -> tuple[str, list[str]]:
    # Negative lookbehind and lookahead to avoid matching dates (2026-08-01) or longer numbers
    pattern = re.compile(r"(?<!\d-)(?<!\d)(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)")
    matches = pattern.findall(text)
    if not matches:
        return text, []
    redacted = pattern.sub("[REDACTED:PHONE]", text)
    return redacted, matches


def rule_email(
    text: str,
    level: str = "mask",
    pseudonym_map: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
    pattern = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")
    matches = pattern.findall(text)
    if not matches:
        return text, []

    if level == "pseudonymize":
        p_map = pseudonym_map if pseudonym_map is not None else {}

        def repl(m: re.Match[str]) -> str:
            raw = m.group(0).lower()
            if raw not in p_map:
                p_map[raw] = f"<person-{len(p_map) + 1}>"
            return p_map[raw]

        redacted = pattern.sub(repl, text)
        return redacted, matches

    redacted = pattern.sub("[REDACTED:EMAIL]", text)
    return redacted, matches


def rule_high_entropy(text: str) -> tuple[str, list[str]]:
    """Detect unclassified high-entropy strings (H > 4.0, len >= 20).

    False-positive guards explicitly preserve git SHAs, UUIDs, and safe tokens.
    """
    pattern = re.compile(
        r"(?<![A-Za-z0-9+/=_\-~!@#$%^&*])[A-Za-z0-9+/=_\-~!@#$%^&*]{20,}(?![A-Za-z0-9+/=_\-~!@#$%^&*])"
    )
    matches: list[str] = []

    def repl(m: re.Match[str]) -> str:
        token = m.group(0)

        # False-positive guard 1: Git SHAs and hexadecimal hashes (at most 16 symbols, entropy <= 4.0)
        if re.fullmatch(r"[0-9a-fA-F]+", token):
            return token

        # False-positive guard 2: UUIDs
        if re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", token
        ):
            return token

        # False-positive guard 3: ULIDs (26-character Crockford Base32)
        if re.fullmatch(r"[0-7][0-9A-HJ-KM-NP-Za-hj-km-np-z]{25}", token):
            return token

        # False-positive guard 4: Already redacted placeholders
        if "[REDACTED" in token or token.startswith("REDACTED") or token.endswith("REDACTED"):
            return token

        # Calculate entropy
        ent = shannon_entropy(token)
        if ent > 4.0:
            matches.append(token)
            return "[REDACTED:HIGH_ENTROPY]"

        return token

    redacted = pattern.sub(repl, text)
    return redacted, matches


def mask_sample(raw: str, rule: str) -> str:
    """Create a safe masked representation of the secret for auditing.

    Never logs or persists the full raw secret.
    """
    raw = raw.strip()
    if rule == "aws_key":
        return f"{raw[:4]}****"
    if rule == "api_key":
        prefix = raw[:7] if len(raw) >= 7 else "sk_****"
        return f"{prefix}****"
    if rule == "github_token":
        return "ghp_****"
    if rule == "slack_token":
        return "xox****"
    if rule == "jwt":
        return "eyJ****"
    if rule == "bearer_token":
        return "Bearer ****"
    if rule == "private_key":
        return "-----BEGIN PRIVATE KEY... [REDACTED]"
    if rule == "db_url":
        # Extract scheme and user, hide password
        m = re.match(r"(?:(\w+)://)?([^:@]+)", raw)
        user = m.group(2) if m else "user"
        return f"{user}:****"
    if rule == "env_var":
        k = raw.split("=")[0].strip() if "=" in raw else "KEY"
        return f"{k}=****"
    if rule == "salary":
        return "$****"
    if rule == "phone":
        return raw[:4] + "****" if len(raw) >= 4 else "+1-555-****"
    if rule == "email":
        parts = raw.split("@")
        if len(parts) == 2:
            return f"{parts[0][:1]}****@{parts[1]}"
        return "d****@domain"
    if rule == "high_entropy":
        return f"{raw[:2]}****{raw[-2:]}" if len(raw) >= 4 else "****"

    return "****"


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------


RULES_PIPELINE: list[tuple[str, Callable[[str], tuple[str, list[str]]]]] = [
    ("private_key", rule_private_key),
    ("aws_key", rule_aws_key),
    ("api_key", rule_api_key),
    ("github_token", rule_github_token),
    ("slack_token", rule_slack_token),
    ("jwt", rule_jwt),
    ("bearer_token", rule_bearer_token),
    ("db_url", rule_db_url),
    ("env_var", rule_env_var),
    ("ip_creds", rule_ip_creds),
    ("salary", rule_salary),
    ("phone", rule_phone),
]


def redact(text: str, *, level: str = "mask") -> RedactionResult:
    """Run all redaction rules in strict precedence order.

    Args:
        text: Raw source text.
        level: "mask" (default) or "pseudonymize" (replaces emails with <person-N>).

    Returns:
        RedactionResult containing the scrubbed text and list of RedactionEventInfo.
    """
    if not text:
        return RedactionResult(text="", events=[])

    current_text = text
    events: list[RedactionEventInfo] = []
    rule_counts: Counter[str] = Counter()
    rule_samples: dict[str, str] = {}

    # 1. Run ordered regex rules
    for rule_name, rule_fn in RULES_PIPELINE:
        current_text, matches = rule_fn(current_text)
        if matches:
            rule_counts[rule_name] += len(matches)
            if rule_name not in rule_samples:
                rule_samples[rule_name] = mask_sample(matches[0], rule_name)

    # 2. Email rule (supports level="pseudonymize")
    pseudonym_map: dict[str, str] = {}
    current_text, email_matches = rule_email(current_text, level=level, pseudonym_map=pseudonym_map)
    if email_matches:
        rule_counts["email"] += len(email_matches)
        if "email" not in rule_samples:
            rule_samples["email"] = mask_sample(email_matches[0], "email")

    # 3. High-entropy scanner (runs after known patterns to minimize false positives)
    current_text, entropy_matches = rule_high_entropy(current_text)
    if entropy_matches:
        rule_counts["high_entropy"] += len(entropy_matches)
        if "high_entropy" not in rule_samples:
            rule_samples["high_entropy"] = mask_sample(entropy_matches[0], "high_entropy")

    for rule, count in rule_counts.items():
        events.append(
            RedactionEventInfo(
                rule=rule,
                count=count,
                span_count=count,
                sample_masked=rule_samples.get(rule, "****"),
            )
        )

    return RedactionResult(text=current_text, events=events)


def redact_text(text: str, *, level: str = "mask") -> tuple[str, list[dict[str, Any]]]:
    """Compatibility adapter for normalizer pipeline."""
    result = redact(text, level=level)
    return result.text, [e.to_dict() for e in result.events]


# ---------------------------------------------------------------------------
# Governance Scan Report
# ---------------------------------------------------------------------------


def scan_report(project: Any, session: Any = None) -> dict[str, Any]:
    """Generate a governance scan report summarizing all redactions for a project."""
    from sqlmodel import Session, func, select

    from ..db import get_engine
    from ..models import Artifact, Project, RedactionEvent

    def _query(sess: Session) -> dict[str, Any]:
        proj_id = project.id if hasattr(project, "id") else str(project)
        proj = sess.get(Project, proj_id)
        proj_name = proj.name if proj else "Unknown"

        # Query redactions joined with artifacts
        stmt = (
            select(RedactionEvent.rule, func.count(RedactionEvent.id))
            .join(Artifact, RedactionEvent.artifact_id == Artifact.id)
            .where(Artifact.project_id == proj_id)
            .group_by(RedactionEvent.rule)
        )
        rule_stats = dict(sess.exec(stmt).all())

        total_redactions = sum(rule_stats.values())
        artifact_count = sess.exec(
            select(func.count(func.distinct(Artifact.id)))
            .join(RedactionEvent, Artifact.id == RedactionEvent.artifact_id)
            .where(Artifact.project_id == proj_id)
        ).one()

        recent_events = sess.exec(
            select(RedactionEvent)
            .join(Artifact, RedactionEvent.artifact_id == Artifact.id)
            .where(Artifact.project_id == proj_id)
            .order_by(RedactionEvent.created_at.desc())
            .limit(20)
        ).all()

        return {
            "project_id": proj_id,
            "project_name": proj_name,
            "total_redactions": total_redactions,
            "redacted_artifacts_count": artifact_count,
            "by_rule": rule_stats,
            "recent_events": [
                {
                    "rule": ev.rule,
                    "sample_masked": ev.sample_masked,
                    "created_at": ev.created_at.isoformat(),
                }
                for ev in recent_events
            ],
        }

    if session is not None:
        return _query(session)
    with Session(get_engine()) as sess:
        return _query(sess)
