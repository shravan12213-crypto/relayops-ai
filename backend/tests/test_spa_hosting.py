"""The built SPA is served by FastAPI: deep links work, API 404s stay 404s."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import configure_test_env


@pytest.fixture()
def built_spa_client(tmp_path, monkeypatch):
    from app import main

    dist = Path(tmp_path) / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>RelayOps shell</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('relayops');", encoding="utf-8")

    configure_test_env(monkeypatch, Path(tmp_path) / "relayops-spa.db")
    monkeypatch.setattr(main, "FRONTEND_DIST", dist)

    with TestClient(main.create_app()) as test_client:
        yield test_client


def test_root_serves_the_shell(built_spa_client: TestClient) -> None:
    response = built_spa_client.get("/")

    assert response.status_code == 200
    assert "RelayOps shell" in response.text


def test_client_side_route_falls_back_to_index(built_spa_client: TestClient) -> None:
    response = built_spa_client.get("/handovers/01HZX/review")

    assert response.status_code == 200
    assert "RelayOps shell" in response.text


def test_assets_are_served_from_dist(built_spa_client: TestClient) -> None:
    response = built_spa_client.get("/assets/app.js")

    assert response.status_code == 200
    assert "relayops" in response.text


def test_api_404_is_not_swallowed_by_the_spa(built_spa_client: TestClient) -> None:
    response = built_spa_client.get("/api/v1/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
