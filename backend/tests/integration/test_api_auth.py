"""Integration tests for authenticated, tenant-scoped API endpoints."""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.middleware.auth import get_current_user


def test_api_v1_endpoints_require_auth(client: TestClient):
    response = client.get("/api/v1/emails")
    assert response.status_code == 401
    assert "authentication required" in response.text.lower()


def test_api_v1_endpoints_succeed_with_valid_user_session(client: TestClient):
    # The endpoint is session-authenticated; an API-wide static key alone is not a user identity.
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="test-user")
    try:
        response = client.get("/api/v1/emails")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    data = response.json()
    assert "emails" in data
    assert "total" in data


def test_public_health_and_ready_endpoints(client: TestClient):
    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"

    ready_response = client.get("/ready")
    assert ready_response.status_code in (200, 503)
