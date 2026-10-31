"""
Security tests for Multi-Factor Authentication (TOTP), enrollment confirmation,
challenge enforcement during login, recovery codes redemption, and single-use constraints.
"""
import pyotp
import pytest
from fastapi.testclient import TestClient
from app.config import settings


def test_mfa_lifecycle_and_challenge(client: TestClient):
    """Test full TOTP enrollment, confirmation, challenge, and recovery flow."""
    email = "mfa_user@example.com"
    password = "StrongPassword123!"

    # 1. Register and log in
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "MFA User", "terms_accepted": True},
    )
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200
    cookies = login_res.cookies

    # 2. Initiate enrollment
    enroll_res = client.post("/api/v1/auth/mfa/enroll", cookies=cookies)
    assert enroll_res.status_code == 200
    enroll_data = enroll_res.json()
    secret = enroll_data["secret"]
    assert secret is not None
    assert "data:image/png;base64," in enroll_data["qr_code"]

    # 3. Confirm with invalid code
    bad_confirm = client.post("/api/v1/auth/mfa/confirm", json={"code": "000000"}, cookies=cookies)
    assert bad_confirm.status_code == 400

    # 4. Confirm with valid code
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()
    confirm_res = client.post("/api/v1/auth/mfa/confirm", json={"code": valid_code}, cookies=cookies)
    assert confirm_res.status_code == 200
    recovery_codes = confirm_res.json()["recovery_codes"]
    assert len(recovery_codes) == 10

    # 5. Log out
    client.post("/api/v1/auth/logout", cookies=cookies)

    # 6. Log in with MFA enabled -> must return mfa_required = True
    mfa_login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert mfa_login.status_code == 200
    assert mfa_login.json()["mfa_required"] is True
    mfa_cookies = mfa_login.cookies

    # 7. Attempting to access protected resource before challenge -> 403 Forbidden
    blocked = client.get("/api/v1/auth/me", cookies=mfa_cookies)
    assert blocked.status_code == 403
    assert "MFA_CHALLENGE_REQUIRED" in blocked.json()["detail"]

    # 8. Submit invalid challenge code
    bad_challenge = client.post("/api/v1/auth/mfa/challenge", json={"code": "999999"}, cookies=mfa_cookies)
    assert bad_challenge.status_code == 400

    # 9. Submit valid challenge code
    good_challenge = client.post("/api/v1/auth/mfa/challenge", json={"code": totp.now()}, cookies=mfa_cookies)
    assert good_challenge.status_code == 200

    # 10. Access protected resource after challenge succeeds
    me_res = client.get("/api/v1/auth/me", cookies=mfa_cookies)
    assert me_res.status_code == 200
    assert me_res.json()["mfa_enabled"] is True

    # 11. Test Recovery Code flow
    # Log out and log in again
    client.post("/api/v1/auth/logout", cookies=mfa_cookies)
    mfa_login2 = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    mfa_cookies2 = mfa_login2.cookies

    # Use first recovery code
    used_rec_code = recovery_codes[0]
    rec_res = client.post(
        "/api/v1/auth/mfa/recovery",
        json={"recovery_code": used_rec_code},
        cookies=mfa_cookies2,
    )
    assert rec_res.status_code == 200

    # Replay of used recovery code fails
    client.post("/api/v1/auth/logout", cookies=mfa_cookies2)
    mfa_login3 = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    bad_rec_replay = client.post(
        "/api/v1/auth/mfa/recovery",
        json={"recovery_code": used_rec_code},
        cookies=mfa_login3.cookies,
    )
    assert bad_rec_replay.status_code == 400

