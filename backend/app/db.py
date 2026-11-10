"""Database engine, session dependency, migrations, and shared DB utilities.

SQLite with WAL mode, foreign keys enabled, busy timeout, ULID generation,
FTS5 search with SQL sensitivity enforcement, and tamper-evident audit logging.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from .config import BACKEND_DIR, get_settings

if TYPE_CHECKING:
    from .models import Artifact, AuditLog

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32
_engine: Engine | None = None
logger = logging.getLogger("relayops.db")


def utcnow() -> datetime:
    """Timezone-aware UTC now. All timestamps are stored in UTC."""
    return datetime.now(UTC)


def new_ulid() -> str:
    """A lexicographically sortable 26-character ULID (48-bit time + 80-bit randomness)."""
    value = (int(time.time() * 1000) << 80) | secrets.randbits(80)
    chars = []
    for shift in range(125, -1, -5):
        chars.append(_ALPHABET[(value >> shift) & 0x1F])
    return "".join(chars)


def resolve_database_url(url: str) -> str:
    """Anchor relative SQLite paths to `backend/`, so the DB is the same file no matter the cwd."""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    raw_path = url[len(prefix) :]
    if raw_path == ":memory:" or raw_path.startswith("/") or ":" in raw_path[:3]:
        return url
    path = Path(raw_path)
    if not path.is_absolute():
        path = (BACKEND_DIR / path).resolve()
    return f"{prefix}{path.as_posix()}"


def get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine

    settings = get_settings()
    url = resolve_database_url(settings.database_url)

    if settings.database_url.startswith("sqlite"):
        db_path = Path(url[len("sqlite:///") :])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args={"check_same_thread": False})
        _install_sqlite_pragmas(_engine)
    else:  # pragma: no cover - the project ships SQLite, but keep the door open
        _engine = create_engine(url)
    return _engine


def _install_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def apply_migrations(engine: Engine) -> None:
    """Scan and apply numbered SQL migrations in ascending order."""
    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL,
                    description TEXT NOT NULL
                );
                """
            )
        )
        applied_rows = conn.execute(text("SELECT version FROM schema_version")).fetchall()
        applied_versions = {row[0] for row in applied_rows}

    migration_files: list[tuple[int, str, Path]] = []
    for file in migrations_dir.glob("*.sql"):
        match = re.match(r"^(\d+)_(.*)\.sql$", file.name)
        if match:
            v_num = int(match.group(1))
            desc = match.group(2).replace("_", " ")
            migration_files.append((v_num, desc, file))

    migration_files.sort(key=lambda x: x[0])

    for v_num, desc, file in migration_files:
        if v_num in applied_versions:
            continue
        sql_content = file.read_text(encoding="utf-8")
        with engine.begin() as conn:
            dbapi_conn = conn.connection.dbapi_connection
            if hasattr(dbapi_conn, "executescript"):
                dbapi_conn.executescript(sql_content)
            else:
                for statement in sql_content.split(";"):
                    stmt = statement.strip()
                    if stmt:
                        conn.execute(text(stmt))
            conn.execute(
                text("INSERT INTO schema_version (version, applied_at, description) VALUES (:v, :at, :desc)"),
                {"v": v_num, "at": utcnow().isoformat(), "desc": desc},
            )
        logger.info("Applied database migration %04d: %s", v_num, desc)


def init_db(engine: Engine | None = None) -> None:
    """Prepare the database, create SQLModel tables, and apply migrations."""
    import app.models  # noqa: F401

    eng = engine or get_engine()
    SQLModel.metadata.create_all(eng)
    apply_migrations(eng)


def db_healthy() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:  # pragma: no cover
        return False


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


# --- Audit logging & cryptographic hash chain ---


def canonical_audit_dict(
    actor_id: str | None,
    action: str,
    target_type: str,
    target_id: str | None,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "action": action,
        "actor_id": actor_id,
        "payload": payload or {},
        "target_id": target_id,
        "target_type": target_type,
    }


def compute_audit_hash(prev_hash: str, canonical_dict: dict[str, Any]) -> str:
    canonical = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((prev_hash + canonical).encode("utf-8")).hexdigest()


def audit(
    session: Session,
    *,
    actor_id: str | None,
    action: str,
    target_type: str,
    target_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditLog:
    """Append a tamper-evident, hash-chained record to audit_log."""
    from .models import AuditLog

    last_entry = session.exec(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1)).first()
    prev_hash = last_entry.hash if last_entry else ""
    c_dict = canonical_audit_dict(actor_id, action, target_type, target_id, payload)
    entry_hash = compute_audit_hash(prev_hash, c_dict)

    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=payload or {},
        prev_hash=prev_hash,
        hash=entry_hash,
        created_at=utcnow(),
    )
    session.add(entry)
    session.flush()
    return entry


def verify_audit_chain_detailed(session: Session) -> dict[str, Any]:
    """Verify that every entry's hash matches its canonical content and links to prev_hash."""
    from .models import AuditLog

    entries = session.exec(select(AuditLog).order_by(AuditLog.seq.asc())).all()
    if not entries:
        return {"valid": True, "entries_count": 0, "tampered_seq": None, "error": None}

    prev_hash = ""
    for entry in entries:
        if entry.prev_hash != prev_hash:
            return {
                "valid": False,
                "entries_count": len(entries),
                "tampered_seq": entry.seq,
                "error": (
                    f"Broken prev_hash chain link at sequence #{entry.seq} "
                    f"(expected {prev_hash[:10]}..., found {entry.prev_hash[:10]}...)"
                ),
            }
        c_dict = canonical_audit_dict(
            entry.actor_id, entry.action, entry.target_type, entry.target_id, entry.payload
        )
        expected_hash = compute_audit_hash(prev_hash, c_dict)
        if entry.hash != expected_hash:
            return {
                "valid": False,
                "entries_count": len(entries),
                "tampered_seq": entry.seq,
                "error": (
                    f"Cryptographic payload hash mismatch at sequence #{entry.seq} " "(row content tampered)"
                ),
            }
        prev_hash = entry.hash

    return {
        "valid": True,
        "entries_count": len(entries),
        "tampered_seq": None,
        "error": None,
    }


def verify_audit_chain(session: Session) -> bool:
    return verify_audit_chain_detailed(session)["valid"]


# --- FTS Search with pre-inference permission firewall ---


def format_fts5_query(query: str) -> str:
    """Extract alphanumeric/word tokens and format for FTS5 prefix matching."""
    tokens = re.findall(r"\w+", query)
    if not tokens:
        return ""
    return " ".join(f'"{token}"*' for token in tokens)


def search_artifacts(
    session: Session,
    *,
    project_id: str,
    query: str,
    max_sensitivity: int = 1,
    limit: int = 20,
) -> list[Artifact]:
    """Search artifacts with mandatory SQL sensitivity filtering."""
    from .models import Artifact

    match_expr = format_fts5_query(query)
    if not match_expr:
        stmt = (
            select(Artifact)
            .where(
                Artifact.project_id == project_id,
                Artifact.sensitivity <= max_sensitivity,
            )
            .order_by(Artifact.valid_time.desc())
            .limit(limit)
        )
        return list(session.exec(stmt).all())

    sql = text(
        """
        SELECT a.id
        FROM artifact_fts f
        JOIN artifact a ON a.rowid = f.rowid
        WHERE artifact_fts MATCH :match_expr
          AND a.project_id = :project_id
          AND a.sensitivity <= :max_sensitivity
        ORDER BY f.rank
        LIMIT :limit
        """
    )
    result = session.connection().execute(
        sql,
        {
            "match_expr": match_expr,
            "project_id": project_id,
            "max_sensitivity": max_sensitivity,
            "limit": limit,
        },
    )
    matched_ids = [row[0] for row in result.fetchall()]
    if not matched_ids:
        return []

    items = session.exec(select(Artifact).where(Artifact.id.in_(matched_ids))).all()
    item_map = {item.id: item for item in items}
    return [item_map[mid] for mid in matched_ids if mid in item_map]


def get_project_by_id_or_slug(session: Session, project_id_or_slug: str) -> Any | None:
    """Resolve a project by either its ULID identifier or unique slug."""
    from .models import Project

    project = session.get(Project, project_id_or_slug)
    if not project:
        project = session.exec(select(Project).where(Project.slug == project_id_or_slug)).first()
    return project
