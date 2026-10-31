"""
Security regression tests for retired legacy OAuth routes and the session-bound V1 flow.
"""
from fastapi.testclient import TestClient


def test_legacy_oauth_routes_are_not_mounted(client: TestClient):
    """Legacy routes without per-user session/state checks must not be exposed."""
    assert client.get("/auth/google/login", follow_redirects=False).status_code == 404
    assert client.get("/auth/google/callback?code=mock_code_abc", follow_redirects=False).status_code == 404


def test_gmail_oauth_callback_rejects_missing_state(client: TestClient):
    """An authenticated Gmail callback without the one-time state cookie is rejected."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "oauth_state_test@example.com",
            "password": "StrongPassword123!",
            "full_name": "OAuth State Test",
            "terms_accepted": True,
        },
    )
    assert reg.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "oauth_state_test@example.com", "password": "StrongPassword123!"},
    )
    assert login.status_code == 200
    callback = client.get(
        "/api/v1/integrations/gmail/callback?code=mock_code_abc&state=attacker-controlled"
    )
    assert callback.status_code == 400
    assert "state" in callback.json()["detail"].lower()
