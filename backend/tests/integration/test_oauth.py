"""
Integration tests for Google OAuth login redirect and callback handling.
"""
from fastapi.testclient import TestClient


def test_oauth_login_redirect(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        "app.services.gmail_service.build_auth_url",
        lambda state=None: ("https://accounts.google.com/o/oauth2/auth?client_id=test", "state_123"),
    )
    resp = client.get("/auth/google/login", follow_redirects=False)
    assert resp.status_code == 307
    assert "accounts.google.com" in resp.headers["location"]


def test_oauth_callback_creates_account(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        "app.api.auth.exchange_code_for_token",
        lambda code: ("student@university.edu", "tokens/gmail_test.json"),
    )
    resp = client.get("/auth/google/callback?code=mock_code_abc", follow_redirects=False)
    assert resp.status_code == 307
    assert "/dashboard" in resp.headers["location"]
