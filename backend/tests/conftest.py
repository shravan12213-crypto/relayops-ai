"""Shared pytest fixtures: an app bound to a throwaway SQLite file per test."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import db
from app.config import get_settings


def configure_test_env(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    """Point settings at a throwaway database and keep tests off the built frontend."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SEED_ON_START", "false")
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("LLM_PROVIDER", "replay")
    get_settings.cache_clear()
    db._engine = None


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Default test environment isolation: throwaway database and replay LLM provider."""
    default_db = tmp_path / "relayops-autouse-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{default_db}")
    monkeypatch.setenv("SEED_ON_START", "false")
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("LLM_PROVIDER", "replay")
    get_settings.cache_clear()
    db._engine = None
    db.init_db()
    yield
    get_settings.cache_clear()
    db._engine = None


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    from app import main

    configure_test_env(monkeypatch, tmp_path / "relayops-test.db")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path / "dist-not-built")

    with TestClient(main.create_app()) as test_client:
        yield test_client

    get_settings.cache_clear()
    db._engine = None


@pytest.fixture()
def session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    configure_test_env(monkeypatch, tmp_path / "relayops-session-test.db")
    db.init_db()
    with Session(db.get_engine()) as sess:
        yield sess

    get_settings.cache_clear()
    db._engine = None
