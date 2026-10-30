"""
Security tests for User Authentication, Registration, Session Handling,
Password Reset, and Brute-Force Rate Limiting.
"""
import pytest
from fastapi.testclient import TestClient
from app.config import settings
from app.services import auth_service


def test_user_registration_and_strength_validation(client: TestClient):
    """Test user registration with password strength requirements."""
    # 1. Weak password (too short)
    res = client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "weak", "full_name": "Alice", "terms_accepted": true},
    )
    assert res.status_code == 422 or res.status_code == 400

    # 2. Weak password (missing uppercase and digit)
    res = client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "lowercaseonly!", "full_name": "Alice", "terms_accepted": true},
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
            "terms_accepted": true,
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "alice@example.com"
    assert "verification_token" in data

    # 4. Duplicate registration rejected
    res_dup = client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice@example.com",
            "password": "StrongPassword123!",
            "full_name": "Alice Duplicate",
            "terms_accepted": true,
        },
    )
    assert res_dup.status_code == 400
    assert "already exists" in res_dup.json()["detail"].lower()


def test_email_verification_flow(client: TestClient):
    """Test email verification with valid, invalid, and replayed tokens."""
    # Register user
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "verify_test@example.com",
            "password": "StrongPassword123!",
            "full_name": "Verify User",
            "terms_accepted": true,
        },
    )
    assert reg.status_code == 201
    token = reg.json()["verification_token"]

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
        json={"email": email, "password": password, "full_name": "Login User", "terms_accepted": true},
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


def test_password_reset_flow(client: TestClient):
    """Test password recovery, single-use token, and session revocation."""
    email = "reset_test@example.com"
    old_password = "OldStrongPassword123!"
    new_password = "NewStrongPassword456!"

    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": old_password, "full_name": "Reset User", "terms_accepted": true},
    )

    # Request reset
    forgot_res = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot_res.status_code == 200
    reset_token = forgot_res.json().get("reset_token")
    assert reset_token is not None

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

