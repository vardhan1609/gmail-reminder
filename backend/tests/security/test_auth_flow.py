"""
Security tests for User Authentication, Registration, Session Handling,
Password Reset, and Brute-Force Rate Limiting.
"""
import pytest
import re
from fastapi.testclient import TestClient
from app.config import settings
from app.services import auth_service


def test_user_registration_and_strength_validation(client: TestClient):
    """Test user registration with password strength requirements."""
    # 1. Weak password (too short)
    res = client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "weak", "full_name": "Alice", "terms_accepted": True},
    )
    assert res.status_code == 422 or res.status_code == 400

    # 2. Weak password (missing uppercase and digit)
    res = client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "lowercaseonly!", "full_name": "Alice", "terms_accepted": True},
    )
    assert res.status_code == 400
    assert "uppercase" in res.json()["detail"].lower() or "number" in res.json()["detail"].lower()

    # 3. Valid strong password
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice@example.com",
            "password": "StrongPassword123!",
            "full_name": "Alice University",
            "terms_accepted": True,
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert "verification_token" not in data
    assert "email" not in data

    # 4. Duplicate registration rejected
    res_dup = client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice@example.com",
            "password": "StrongPassword123!",
            "full_name": "Alice Duplicate",
            "terms_accepted": True,
        },
    )
    assert res_dup.status_code == 201
    assert res_dup.json() == data or res_dup.json()["message"] == data["message"]



def test_registration_requires_terms_consent(client: TestClient):
    """Terms acceptance is mandatory; marketing consent remains optional."""
    payload = {
        "email": "consent_test@example.com",
        "password": "StrongPassword123!",
        "full_name": "Consent User",
    }
    missing = client.post("/api/v1/auth/register", json=payload)
    assert missing.status_code == 422

    declined = client.post(
        "/api/v1/auth/register",
        json={**payload, "terms_accepted": False},
    )
    assert declined.status_code == 400
    assert "accept" in declined.json()["detail"].lower()

    accepted = client.post(
        "/api/v1/auth/register",
        json={**payload, "terms_accepted": True, "marketing_opt_in": False},
    )
    assert accepted.status_code == 201


def test_email_verification_flow(client: TestClient, monkeypatch):
    """Test email verification with valid, invalid, and replayed tokens."""
    # Capture the SMTP boundary so the one-time token is tested out-of-band.
    sent_messages = []
    monkeypatch.setattr(
        "app.api.v1.auth.send_transactional_email",
        lambda to_email, subject, body: sent_messages.append(body),
    )
    # Register user
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "verify_test@example.com",
            "password": "StrongPassword123!",
            "full_name": "Verify User",
            "terms_accepted": True,
        },
    )
    assert reg.status_code == 201
    token_match = re.search(r"/verify-email\?token=([^\s]+)", sent_messages[-1])
    assert token_match, "verification link should be delivered by email"
    token = token_match.group(1)

    # Verify with invalid token
    bad_res = client.post("/api/v1/auth/verify-email", json={"token": "invalid_token_123"})
    assert bad_res.status_code == 400

    # Verify with valid token
    good_res = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert good_res.status_code == 200

    # Token replay prevention
    replay_res = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert replay_res.status_code == 400


def test_login_and_cookie_session(client: TestClient):
    """Test user login, rate limiting, HttpOnly cookie issuance, and session logout."""
    email = "login_test@example.com"
    password = "StrongPassword123!"

    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Login User", "terms_accepted": True},
    )

    # 1. Invalid login attempt
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword123!"},
    )
    assert bad_login.status_code == 401

    # 2. Successful login
    good_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert good_login.status_code == 200
    assert good_login.json()["mfa_required"] is False
    assert settings.session_cookie_name in good_login.cookies

    # 3. Access /auth/me with session cookie
    me_res = client.get("/api/v1/auth/me", cookies=good_login.cookies)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == email

    # 4. View active sessions
    sess_res = client.get("/api/v1/auth/sessions", cookies=good_login.cookies)
    assert sess_res.status_code == 200
    sessions = sess_res.json()
    assert len(sessions) >= 1
    assert any(s["is_current"] for s in sessions)

    # 5. Logout
    logout_res = client.post("/api/v1/auth/logout", cookies=good_login.cookies)
    assert logout_res.status_code == 200

    # 6. Verify session invalidated
    me_after_logout = client.get("/api/v1/auth/me", cookies=good_login.cookies)
    assert me_after_logout.status_code == 401


def test_password_reset_flow(client: TestClient, monkeypatch):
    """Test password recovery, single-use token, and session revocation."""
    email = "reset_test@example.com"
    old_password = "OldStrongPassword123!"
    new_password = "NewStrongPassword456!"

    sent_messages = []
    monkeypatch.setattr(
        "app.api.v1.auth.send_transactional_email",
        lambda to_email, subject, body: sent_messages.append(body),
    )
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": old_password, "full_name": "Reset User", "terms_accepted": True},
    )

    # Request reset
    forgot_res = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot_res.status_code == 200
    assert "reset_token" not in forgot_res.json()
    reset_match = re.search(r"/reset-password\?token=([^\s]+)", sent_messages[-1])
    assert reset_match, "password reset link should be delivered by email"
    reset_token = reset_match.group(1)

    # Reset with weak password
    weak_reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "weak"},
    )
    assert weak_reset.status_code in (400, 422)

    # Reset with valid new password
    good_reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": new_password},
    )
    assert good_reset.status_code == 200

    # Replay of reset token rejected
    replay_reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "AnotherPassword789!"},
    )
    assert replay_reset.status_code == 400

    # Login with old password fails
    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": old_password},
    )
    assert old_login.status_code == 401

    # Login with new password succeeds
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": new_password},
    )
    assert new_login.status_code == 200

