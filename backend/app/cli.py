"""Command-line entry point: `python -m app.cli <command>`.

Commands:
- seed: load the PayFlow demo project, users and artifacts.
- reset-db: drop all tables and recreate clean schema with migrations.
- record-llm: record LLM requests for the seed dataset into replay recordings.
- verify-chain: verify the cryptographic audit hash chain integrity.
- create-user: create a new user account with hashed password.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def cmd_seed(_: argparse.Namespace) -> int:
    """Seed the PayFlow demo dataset."""
    from sqlmodel import Session

    from app.db import get_engine, init_db
    from app.routers.sources import execute_demo_load

    init_db()
    with Session(get_engine()) as session:
        proj, counts, total = execute_demo_load(session, seed_workflows=True)
        print(f"[OK] Seeded project '{proj.name}' ({proj.id}) with {total} artifacts: {counts}")
    return 0


def cmd_reset_db(_: argparse.Namespace) -> int:
    """Drop and recreate all database tables and apply migrations."""
    from sqlmodel import SQLModel

    import app.models  # noqa: F401
    from app.db import get_engine, init_db

    engine = get_engine()
    SQLModel.metadata.drop_all(engine)
    init_db(engine)
    print("[OK] Database reset successfully: all tables dropped, recreated, and migrations applied.")
    return 0


def cmd_record_llm(_: argparse.Namespace) -> int:
    """Record LLM calls against seed data for zero-key replay mode."""
    from app.llm import cli_record

    cli_record()
    print("[OK] LLM recordings generated successfully.")
    return 0


def cmd_verify_chain(_: argparse.Namespace) -> int:
    """Verify cryptographic audit hash chain in database."""
    from sqlmodel import Session

    from app.db import get_engine, init_db, verify_audit_chain_detailed

    init_db()
    with Session(get_engine()) as session:
        res = verify_audit_chain_detailed(session)
        if res["valid"]:
            count = res["entries_count"]
            print(f"[OK] Audit log cryptographic hash chain is valid and untampered ({count} entries).")
            return 0
        else:
            t_seq = res["tampered_seq"]
            t_err = res["error"]
            print(
                f"[FAIL] Audit log cryptographic hash chain verification FAILED! "
                f"Tampering detected at sequence #{t_seq}: {t_err}"
            )
            return 1


def cmd_tamper(_: argparse.Namespace) -> int:
    """Intentionally tamper with an audit log row to test integrity verification."""
    from sqlmodel import Session, select

    from app.db import get_engine, init_db
    from app.models import AuditLog

    init_db()
    with Session(get_engine()) as session:
        target = session.exec(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1)).first()
        if not target:
            print("[ERROR] No audit log entries found to tamper.")
            return 1
        target.payload = {"tampered": True, "unauthorized_change": "hacked"}
        session.add(target)
        session.commit()
        print(f"[OK] Tampered audit log entry at seq {target.seq} (Action: {target.action}).")
        return 0


def cmd_create_user(args: argparse.Namespace) -> int:
    """Create a new user with scrypt hashed password."""
    from sqlmodel import Session, select

    from app.auth import hash_password
    from app.db import get_engine, init_db
    from app.models import User

    init_db()
    with Session(get_engine()) as session:
        existing = session.exec(select(User).where(User.email == args.email.lower())).first()
        if existing:
            print(f"[ERROR] User with email '{args.email}' already exists.")
            return 1

        user = User(
            email=args.email.lower(),
            name=args.name,
            password_hash=hash_password(args.password),
            role=args.role,
            clearance=args.clearance,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        print(
            f"[OK] Created user {user.email} (ID: {user.id}, Role: {user.role}, Clearance: {user.clearance})"
        )
        return 0


def cmd_backup(args: argparse.Namespace) -> int:
    """Safely backup the SQLite database using sqlite3 online backup API."""
    import sqlite3
    from datetime import UTC, datetime
    from pathlib import Path

    from app.config import get_settings
    from app.db import resolve_database_url

    settings = get_settings()
    if not settings.is_sqlite:
        print("[ERROR] Database backup is only supported for SQLite databases.")
        return 1

    resolved_url = resolve_database_url(settings.database_url)
    prefix = "sqlite:///"
    if not resolved_url.startswith(prefix):
        print(f"[ERROR] Could not resolve SQLite path from '{settings.database_url}'")
        return 1

    src_path = Path(resolved_url[len(prefix) :])
    if not src_path.exists():
        print(f"[ERROR] Database file not found at '{src_path}'")
        return 1

    if getattr(args, "dest", None):
        dest_path = Path(args.dest)
    else:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        dest_path = src_path.parent / f"backup_{src_path.stem}_{timestamp}.db"

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Creating safe online backup from '{src_path}' to '{dest_path}'...")

    src_conn = sqlite3.connect(src_path)
    try:
        dst_conn = sqlite3.connect(dest_path)
        try:
            with dst_conn:
                src_conn.backup(dst_conn, pages=100)
            print(f"[OK] Backup completed successfully: {dest_path} ({dest_path.stat().st_size} bytes)")
            return 0
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="relayops", description="RelayOps CLI maintenance commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. seed
    seed_p = subparsers.add_parser("seed", help="load the PayFlow demo project, users and artifacts")
    seed_p.set_defaults(func=cmd_seed)

    # 2. reset-db
    reset_p = subparsers.add_parser("reset-db", help="drop all tables, recreate schema and run migrations")
    reset_p.set_defaults(func=cmd_reset_db)

    # 3. record-llm
    record_p = subparsers.add_parser("record-llm", help="record LLM cache entries for seed data replay")
    record_p.set_defaults(func=cmd_record_llm)

    # 4. verify-chain
    verify_p = subparsers.add_parser("verify-chain", help="verify audit log cryptographic hash chain")
    verify_p.set_defaults(func=cmd_verify_chain)

    # 4b. tamper (testing tool)
    tamper_p = subparsers.add_parser(
        "tamper", help="intentionally tamper an audit log row for integrity testing"
    )
    tamper_p.set_defaults(func=cmd_tamper)

    # 5. create-user
    user_p = subparsers.add_parser("create-user", help="create a new user account with hashed password")
    user_p.add_argument("--email", required=True, help="User email address")
    user_p.add_argument("--name", required=True, help="User full name")
    user_p.add_argument("--password", required=True, help="User password")
    user_p.add_argument(
        "--role",
        default="successor",
        choices=["lead", "outgoing", "successor", "contractor", "auditor"],
        help="User role (default: successor)",
    )
    user_p.add_argument(
        "--clearance",
        type=int,
        default=0,
        choices=[0, 1, 2, 3],
        help="User sensitivity clearance level 0-3 (default: 0)",
    )
    user_p.set_defaults(func=cmd_create_user)

    # 6. backup
    backup_p = subparsers.add_parser("backup", help="safely backup SQLite database using online backup API")
    backup_p.add_argument("--dest", default=None, help="Destination file path for the backup (optional)")
    backup_p.set_defaults(func=cmd_backup)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
