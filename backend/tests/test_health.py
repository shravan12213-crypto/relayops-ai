"""The health endpoint is the contract every deploy check and smoke script relies on."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_reports_ok_and_llm_mode(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["llm_mode"] in {"replay", "anthropic", "openai"}
    assert body["version"]


def test_health_always_returns_a_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert len(response.headers["X-Request-ID"]) >= 8


def test_incoming_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "judge-run-42"})

    assert response.headers["X-Request-ID"] == "judge-run-42"


def test_unknown_route_uses_the_standard_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["message"]
    assert error["details"]["request_id"] == response.headers["X-Request-ID"]


def test_openapi_schema_is_served(client: TestClient) -> None:
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/health" in response.json()["paths"]
