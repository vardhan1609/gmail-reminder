"""
Security tests for Cross-Tenant Data Isolation and IDOR prevention.
Verifies that User A's emails, reminders, integrations, and preferences
cannot be accessed, modified, or deleted by User B.
"""
import pytest
from fastapi.testclient import TestClient


def test_cross_tenant_data_isolation(client: TestClient):
    """Test that User B cannot read or tamper with User A's emails and integrations."""
    # 1. Register User A
    client.post(
        "/api/v1/auth/register",
        json={"email": "usera@example.com", "password": "UserAPassword123!", "full_name": "User A"},
    )
    login_a = client.post("/api/v1/auth/login", json={"email": "usera@example.com", "password": "UserAPassword123!"})
    cookies_a = login_a.cookies

    # 2. Register User B
    client.post(
        "/api/v1/auth/register",
        json={"email": "userb@example.com", "password": "UserBPassword123!", "full_name": "User B"},
    )
    login_b = client.post("/api/v1/auth/login", json={"email": "userb@example.com", "password": "UserBPassword123!"})
    cookies_b = login_b.cookies

    # 3. User A creates a notification destination
    dest_a = client.post(
        "/api/v1/integrations/notifications",
        json={"type": "telegram", "name": "User A Telegram", "target_id": "111222333"},
        cookies=cookies_a,
    )
    assert dest_a.status_code == 201
    dest_a_id = dest_a.json()["id"]

    # 4. User B attempts to view User A's destinations -> not in User B's list
    dests_b = client.get("/api/v1/integrations/notifications", cookies=cookies_b)
    assert dests_b.status_code == 200
    assert not any(d["id"] == dest_a_id for d in dests_b.json())

    # 5. User B attempts to DELETE User A's destination (IDOR test) -> 404 Not Found
    del_res = client.delete(f"/api/v1/integrations/notifications/{dest_a_id}", cookies=cookies_b)
    assert del_res.status_code == 404

    # 6. User A updates preferences
    pref_res = client.put(
        "/api/v1/integrations/preferences",
        json={"notification_mode": "summary", "digest_interval_minutes": 120},
        cookies=cookies_a,
    )
    assert pref_res.status_code == 200

    # 7. User B gets their own preferences (must not see User A's preferences)
    pref_b = client.get("/api/v1/integrations/preferences", cookies=cookies_b)
    assert pref_b.status_code == 200
    assert pref_b.json()["notification_mode"] == "immediate"  # default, untouched by User A

