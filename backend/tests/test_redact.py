"""Tests for secrets and PII redaction engine (P06).

Validates:
- Every named redaction rule (table-driven)
- Pseudonymization mode (stable per-document email mapping)
- False-positive guards (0 SHAs/UUIDs/ULIDs damaged, dates preserved)
- 100% detection of planted ground-truth secrets
- Redaction idempotence (redact(redact(x)) == redact(x))
- Performance benchmark (1MB in < 1.0s)
- Governance scan_report generation
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlmodel import Session

from app.ingest.redact import (
    mask_sample,
    redact,
    redact_text,
    rule_api_key,
    rule_aws_key,
    rule_bearer_token,
    rule_db_url,
    rule_email,
    rule_env_var,
    rule_github_token,
    rule_high_entropy,
    rule_ip_creds,
    rule_jwt,
    rule_phone,
    rule_private_key,
    rule_salary,
    rule_slack_token,
    scan_report,
    shannon_entropy,
)
from app.models import Artifact, Project, RedactionEvent, Source

# ---------------------------------------------------------------------------
# 1. Table-Driven Unit Tests for Individual Rules
# ---------------------------------------------------------------------------


def test_rule_aws_key() -> None:
    text = "Deploying with AKIA1234567890ABCDEF and backup ASIA9876543210FEDCBA."
    redacted, matches = rule_aws_key(text)
    assert len(matches) == 2
    assert "AKIA1234567890ABCDEF" in matches
    assert "ASIA9876543210FEDCBA" in matches
    assert "AKIA" not in redacted
    assert "[REDACTED:AWS_KEY]" in redacted


def test_rule_api_key() -> None:
    text = "Keys: sk_live_abcdef1234567890_live and sk_test_99a8b7c6d5e4f3a2b1_test."
    redacted, matches = rule_api_key(text)
    assert len(matches) == 2
    assert "sk_live_" not in redacted
    assert "sk_test_" not in redacted
    assert redacted.count("[REDACTED:API_KEY]") == 2


def test_rule_github_token() -> None:
    text = (
        "Personal token: ghp_1234567890abcdefghijklmnopqrstuvwxyz12, "
        "fine-grained: github_pat_11ABCD_efghijklmnopqrstuvwxyz1234567890, "
        "oauth: gho_1234567890abcdefghijklmnopqrstuvwxyz12"
    )
    redacted, matches = rule_github_token(text)
    assert len(matches) == 3
    assert "ghp_" not in redacted
    assert "github_pat_" not in redacted
    assert "gho_" not in redacted
    assert redacted.count("[REDACTED:GITHUB_TOKEN]") == 3


def test_rule_slack_token() -> None:
    text = "Bot token: xoxb-1234567890-abcdefghijkl and user token xoxp-9876543210-zyxwvutsrq."
    redacted, matches = rule_slack_token(text)
    assert len(matches) == 2
    assert "xoxb-" not in redacted
    assert "xoxp-" not in redacted
    assert redacted.count("[REDACTED:SLACK_TOKEN]") == 2


def test_rule_jwt() -> None:
    text = (
        "Authorization header contains eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c in session cookie."
    )
    redacted, matches = rule_jwt(text)
    assert len(matches) == 1
    assert "eyJhbGci" not in redacted
    assert "[REDACTED:JWT]" in redacted


def test_rule_bearer_token() -> None:
    text = "Request headers: Bearer my_secret_token_1234567890_test."
    redacted, matches = rule_bearer_token(text)
    assert len(matches) == 1
    assert "my_secret_token" not in redacted
    assert "Bearer [REDACTED:TOKEN]." in redacted


def test_rule_private_key() -> None:
    sample_key = (
        "-----BEGIN RSA PRIVATE KEY-----\n" "MIIEowIBAAKCAQEA04sV2...\n" "-----END RSA PRIVATE KEY-----"
    )
    text = f"Server certificate:\n{sample_key}\nStored on disk."
    redacted, matches = rule_private_key(text)
    assert len(matches) == 1
    assert sample_key not in redacted
    assert "[REDACTED:PRIVATE_KEY]" in redacted


def test_rule_db_url() -> None:
    text = (
        "Connect to postgres://payflow_user:super_secret_pw123@db.internal:5432/payflow_prod for migration."
    )
    redacted, matches = rule_db_url(text)
    assert len(matches) == 1
    assert "super_secret_pw123" not in redacted
    assert "payflow_user:[REDACTED:PASSWORD]@db.internal:5432/payflow_prod" in redacted


def test_rule_env_var() -> None:
    text = (
        "WEBHOOK_SECRET=whsec_abc1234567890\n"
        "export DB_PASSWORD='my_prod_password_99'\n"
        "NORMAL_VAR=hello_world\n"
        'API_KEY="secret_api_key_44321"\n'
    )
    redacted, matches = rule_env_var(text)
    assert len(matches) == 3
    assert "whsec_abc1234567890" not in redacted
    assert "my_prod_password_99" not in redacted
    assert "secret_api_key_44321" not in redacted
    assert "NORMAL_VAR=hello_world" in redacted
    assert "WEBHOOK_SECRET=[REDACTED:SECRET]" in redacted


def test_rule_ip_creds() -> None:
    text = "Access internal service at http://admin:p@ssw0rd99@192.168.1.100:8080/metrics."
    redacted, matches = rule_ip_creds(text)
    assert len(matches) == 1
    assert "p@ssw0rd99" not in redacted
    assert "http://admin:[REDACTED:PASSWORD]@192.168.1.100:8080/metrics" in redacted


def test_rule_salary() -> None:
    cases = [
        ("Salary approved at $185,000 for senior lead.", "[REDACTED:COMPENSATION]"),
        ("Contractor rate approved at $150k annualized.", "[REDACTED:COMPENSATION]"),
        ("Bonus awarded: 50,000 USD bonus.", "[REDACTED:COMPENSATION]"),
        ("CTC of £75,000 offered.", "[REDACTED:COMPENSATION]"),
        ("$185,000", "[REDACTED:COMPENSATION]"),
    ]
    for input_text, expected_token in cases:
        redacted, matches = rule_salary(input_text)
        assert len(matches) >= 1, f"Failed on input: {input_text}"
        assert expected_token in redacted, f"Expected {expected_token} in {redacted}"


def test_rule_phone() -> None:
    cases = [
        "Call VP at +1-555-019-2834 tomorrow.",
        "Emergency phone: (555) 019-2834.",
        "Direct dial: 555-019-2834.",
    ]
    for text in cases:
        redacted, matches = rule_phone(text)
        assert len(matches) == 1
        assert "[REDACTED:PHONE]" in redacted


def test_rule_email() -> None:
    text = "Contact akulkarni@payflow.dev or mpatel@payflow.dev."
    redacted, matches = rule_email(text, level="mask")
    assert len(matches) == 2
    assert "akulkarni@payflow.dev" not in redacted
    assert "mpatel@payflow.dev" not in redacted
    assert redacted.count("[REDACTED:EMAIL]") == 2


def test_rule_high_entropy() -> None:
    # High entropy base64 token (len >= 20, entropy > 4.0)
    high_entropy_token = "4kL9#mP!2zQ$8vR@5xW&3yB*"
    text = f"Session nonce: {high_entropy_token} in trace."
    redacted, matches = rule_high_entropy(text)
    assert len(matches) == 1
    assert high_entropy_token not in redacted
    assert "[REDACTED:HIGH_ENTROPY]" in redacted


# ---------------------------------------------------------------------------
# 2. Shannon Entropy & Mask Sample Utilities
# ---------------------------------------------------------------------------


def test_shannon_entropy_calculation() -> None:
    assert shannon_entropy("") == 0.0
    assert shannon_entropy("AAAAAA") == 0.0
    # Two symbols equally distributed -> 1.0 bit
    assert pytest.approx(shannon_entropy("ABABABAB"), 0.01) == 1.0
    # Hexadecimal SHA with at most 16 symbols has theoretical max log2(16) = 4.0
    hex_sha = "c1a0110000000000000000000000000000000080"
    assert shannon_entropy(hex_sha) <= 4.0


def test_mask_sample_never_stores_original() -> None:
    samples = [
        ("aws_key", "AKIA1234567890ABCDEF", "AKIA****"),
        ("api_key", "sk_test_1234567890abcdef", "sk_test****"),
        ("github_token", "ghp_1234567890abcdef", "ghp_****"),
        ("slack_token", "xoxb-1234567890", "xox****"),
        ("jwt", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "eyJ****"),
        ("bearer_token", "Bearer my_secret_token", "Bearer ****"),
        ("salary", "$185,000", "$****"),
        ("email", "akulkarni@payflow.dev", "a****@payflow.dev"),
        ("phone", "+1-555-019-2834", "+1-5****"),
    ]
    for rule, raw, expected_prefix in samples:
        masked = mask_sample(raw, rule)
        assert raw not in masked
        assert masked.startswith(expected_prefix.split("*")[0])


# ---------------------------------------------------------------------------
# 3. Pseudonymization Mode
# ---------------------------------------------------------------------------


def test_pseudonymize_level_stable_per_document() -> None:
    text = (
        "Send message to akulkarni@payflow.dev and cc mpatel@payflow.dev. "
        "If no reply, ping akulkarni@payflow.dev again."
    )
    result = redact(text, level="pseudonymize")
    assert "akulkarni@payflow.dev" not in result.text
    assert "mpatel@payflow.dev" not in result.text
    assert "<person-1>" in result.text
    assert "<person-2>" in result.text
    # Stable mapping: akulkarni appears twice as <person-1>
    assert result.text.count("<person-1>") == 2
    assert result.text.count("<person-2>") == 1


# ---------------------------------------------------------------------------
# 4. False-Positive Guards (0 SHAs/UUIDs/ULIDs damaged, dates preserved)
# ---------------------------------------------------------------------------


def test_false_positive_guards() -> None:
    commit_sha_40 = "c1a0110000000000000000000000000000000080"
    short_sha_7 = "c1a0110"
    uuid_val = "550e8400-e29b-41d4-a716-446655440000"
    ulid_val = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    date_val = "2026-08-01"
    timestamp_val = "2026-10-26T09:15:00Z"
    order_amount = "Fixed cart order calculation for $50.00 total."
    stale_var_name = "Deprecated setting STRIPE_WEBHOOK_SECRET_OLD in runbook."
    already_redacted = "[REDACTED:API_KEY] and [REDACTED:AWS_KEY]"

    doc = (
        f"Commit {commit_sha_40} (short {short_sha_7}) by {uuid_val} "
        f"on {date_val} at {timestamp_val}.\n"
        f"Entity ULID: {ulid_val}.\n"
        f"{order_amount}\n"
        f"{stale_var_name}\n"
        f"{already_redacted}\n"
    )

    res = redact(doc)

    # 100% preservation of identifiers and non-secret amounts
    assert commit_sha_40 in res.text
    assert short_sha_7 in res.text
    assert uuid_val in res.text
    assert ulid_val in res.text
    assert date_val in res.text
    assert timestamp_val in res.text
    assert "$50.00" in res.text
    assert "STRIPE_WEBHOOK_SECRET_OLD" in res.text
    assert "[REDACTED:API_KEY]" in res.text
    assert "[REDACTED:AWS_KEY]" in res.text


# ---------------------------------------------------------------------------
# 5. Planted Ground-Truth Secrets (100% Detection)
# ---------------------------------------------------------------------------


def test_all_planted_secrets_detected() -> None:
    gt_path = Path("backend/seed/ground_truth.json")
    if not gt_path.exists():
        gt_path = Path("seed/ground_truth.json")
    assert gt_path.exists(), "ground_truth.json must exist"

    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    planted_secrets = gt.get("planted_secrets", [])
    assert len(planted_secrets) >= 7

    for secret in planted_secrets:
        raw_val = secret["raw"]
        kind = secret["kind"]
        loc = secret["location"]

        # 1. Direct redaction of secret value or phrase
        res = redact(raw_val)
        if kind == "db_url":
            # For db_url, password is scrubbed while scheme/user are kept
            assert "fake_password_12345" not in res.text
        else:
            assert raw_val not in res.text, f"Secret of kind '{kind}' was not redacted: {raw_val}"

        # 2. Verify in source artifact file
        source_file, msg_id = loc.split(":")
        file_path = Path(f"backend/seed/data/{source_file}")
        if not file_path.exists():
            file_path = Path(f"seed/data/{source_file}")
        assert file_path.exists(), f"Source file {source_file} must exist"

        data = json.loads(file_path.read_text(encoding="utf-8"))
        # Find the message text
        msg_text = None
        for thread in data:
            if thread.get("root", {}).get("message_id") == msg_id:
                msg_text = thread["root"]["text"]
                break
            for rep in thread.get("replies", []):
                if rep.get("message_id") == msg_id:
                    msg_text = rep["text"]
                    break
            if msg_text:
                break

        assert msg_text is not None, f"Could not find message {msg_id} in {source_file}"
        scrubbed = redact(msg_text)
        if kind == "db_url":
            assert "fake_password_12345" not in scrubbed.text
        else:
            assert (
                raw_val not in scrubbed.text
            ), f"Planted secret {raw_val} still present in scrubbed message {msg_id}"


# ---------------------------------------------------------------------------
# 6. Idempotence
# ---------------------------------------------------------------------------


def test_redaction_idempotence() -> None:
    mixed_text = (
        "# Staging Deployment Runbook\n\n"
        "Configured by akulkarni@payflow.dev on 2026-10-15.\n"
        "Primary AWS key: AKIAFAKE12345EXAMPLE\n"
        "Database URL: postgres://payflow_user:fake_password_12345@db.internal:5432/payflow_prod\n"
        "API Secret: sk_test_FAKE_payflow_webhook_99a8b7c6d5e4f3a2b1\n"
        "Contact: +1-555-019-2834\n"
        "Lead compensation rate approved at $185,000 annualized.\n"
        "Commit SHA: c1a0110000000000000000000000000000000080\n"
        "UUID: 550e8400-e29b-41d4-a716-446655440000\n"
        "ULID: 01ARZ3NDEKTSV4RRFFQ69G5FAV\n"
    )

    pass1 = redact(mixed_text)
    pass2 = redact(pass1.text)

    # Output text is identical
    assert pass1.text == pass2.text
    # Second pass creates zero new redaction events
    assert len(pass2.events) == 0


# ---------------------------------------------------------------------------
# 7. Performance Benchmark (1MB in < 1.0s)
# ---------------------------------------------------------------------------


def test_performance_1mb() -> None:
    # Build 1MB of realistic mixed text
    paragraph = (
        "## Sprint Review Notes\n"
        "The team completed pull request #89 migrating sessions to stateless JWT.\n"
        "Reviewers: mpatel@payflow.dev, akulkarni@payflow.dev.\n"
        "Commit c1a0110000000000000000000000000000000072 was merged successfully.\n"
        "Metrics showed latency improvement from 120ms to 45ms across all webhooks.\n"
        "No database migrations were required; redis session cache was deprecated.\n"
        "UUID tracker: 550e8400-e29b-41d4-a716-446655440000 on node 01ARZ3NDEKTSV4RRFFQ69G5FAV.\n"
        "Config check: STRIPE_WEBHOOK_SECRET_OLD remains in fallback mode.\n\n"
    )
    # Repeat until >= 1MB (1,048,576 bytes)
    repeats = (1024 * 1024 // len(paragraph.encode("utf-8"))) + 5
    large_text = paragraph * repeats
    assert len(large_text.encode("utf-8")) >= 1024 * 1024

    t0 = time.perf_counter()
    res = redact(large_text)
    t1 = time.perf_counter()
    elapsed = t1 - t0

    assert elapsed < 1.0, f"Redaction took too long: {elapsed:.3f}s for 1MB"
    assert "mpatel@payflow.dev" not in res.text


# ---------------------------------------------------------------------------
# 8. Governance Scan Report
# ---------------------------------------------------------------------------


def test_scan_report(session: Session) -> None:
    project = Project(
        name="Scan Test Project",
        slug="scan-test",
        description="Testing scan report",
        status="active",
    )
    session.add(project)
    session.commit()
    session.refresh(project)

    source = Source(
        project_id=project.id,
        type="slack_json",
        name="Test Channel",
        config={},
        status="active",
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    art = Artifact(
        project_id=project.id,
        source_id=source.id,
        kind="chat_thread",
        external_id="th_scan_01",
        source_uri="slack://test",
        title="Redacted Thread",
        body_redacted="Redacted text with [REDACTED:API_KEY]",
        body_hash="hash123",
        author_alias="dev",
        valid_time=datetime.now(UTC),
        sensitivity=1,
        authority=0.4,
        redaction_count=2,
    )
    session.add(art)
    session.commit()
    session.refresh(art)

    ev1 = RedactionEvent(
        artifact_id=art.id,
        rule="api_key",
        count=1,
        sample_masked="sk_test_****",
    )
    ev2 = RedactionEvent(
        artifact_id=art.id,
        rule="aws_key",
        count=1,
        sample_masked="AKIA****",
    )
    session.add(ev1)
    session.add(ev2)
    session.commit()

    report = scan_report(project, session=session)
    assert report["project_id"] == project.id
    assert report["project_name"] == "Scan Test Project"
    assert report["total_redactions"] == 2
    assert report["redacted_artifacts_count"] == 1
    assert report["by_rule"]["api_key"] == 1
    assert report["by_rule"]["aws_key"] == 1
    assert len(report["recent_events"]) == 2


def test_redact_text_adapter() -> None:
    text = "Secret: sk_test_1234567890abcdef_key."
    redacted_body, events = redact_text(text)
    assert "[REDACTED:API_KEY]" in redacted_body
    assert len(events) == 1
    assert events[0]["rule"] == "api_key"
    assert events[0]["sample_masked"] == "sk_test****"
