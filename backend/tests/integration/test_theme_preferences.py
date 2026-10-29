"""
Integration tests for user theme preferences and persistence.
Validates light, dark, and system modes, invalid inputs, and tenant isolation.
"""
import pytest
from fastapi.testclient import TestClient


def test_theme_preference_default_and_updates(client: TestClient):
    """Test retrieving default theme and updating to light, dark, system."""
    # 1. Register and login a user
    client.post(
        "/api/v1/auth/register",
        json={"email": "themeuser@example.com", "password": "SecurePassword123!", "full_name": "Theme User"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "themeuser@example.com", "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    cookies = login_res.cookies

    # 2. Get default preferences -> theme_preference must be 'system'
    get_res = client.get("/api/v1/integrations/preferences", cookies=cookies)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["theme_preference"] == "system"

    # 3. Update to 'dark'
    put_dark = client.put(
        "/api/v1/integrations/preferences",
        json={"theme_preference": "dark"},
        cookies=cookies,
    )
    assert put_dark.status_code == 200
    assert put_dark.json()["theme_preference"] == "dark"

    # Verify persisted on subsequent GET
    get_dark = client.get("/api/v1/integrations/preferences", cookies=cookies)
    assert get_dark.json()["theme_preference"] == "dark"

    # 4. Update to 'light'
    put_light = client.put(
        "/api/v1/integrations/preferences",
        json={"theme_preference": "light"},
        cookies=cookies,
    )
    assert put_light.status_code == 200
    assert put_light.json()["theme_preference"] == "light"

    # 5. Update to 'system'
    put_system = client.put(
        "/api/v1/integrations/preferences",
        json={"theme_preference": "system"},
        cookies=cookies,
    )
    assert put_system.status_code == 200
    assert put_system.json()["theme_preference"] == "system"


def test_theme_preference_invalid_value_rejected(client: TestClient):
    """Test that invalid theme values return 400 Bad Request."""
    client.post(
        "/api/v1/auth/register",
        json={"email": "invalidtheme@example.com", "password": "SecurePassword123!", "full_name": "Invalid Theme User"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "invalidtheme@example.com", "password": "SecurePassword123!"},
    )
    cookies = login_res.cookies

    # Attempt to set invalid theme
    put_invalid = client.put(
        "/api/v1/integrations/preferences",
        json={"theme_preference": "neon-glow"},
        cookies=cookies,
    )
    assert put_invalid.status_code == 400
    assert "Invalid theme preference" in put_invalid.json()["detail"]


def test_theme_preference_tenant_isolation(client: TestClient):
    """Test that User A updating theme does not affect User B's preference."""
    # User 1
    client.post(
        "/api/v1/auth/register",
        json={"email": "tenant_theme_1@example.com", "password": "SecurePassword123!", "full_name": "Tenant 1"},
    )
    login_1 = client.post(
        "/api/v1/auth/login",
        json={"email": "tenant_theme_1@example.com", "password": "SecurePassword123!"},
    )
    cookies_1 = login_1.cookies

    # User 2
    client.post(
        "/api/v1/auth/register",
        json={"email": "tenant_theme_2@example.com", "password": "SecurePassword123!", "full_name": "Tenant 2"},
    )
    login_2 = client.post(
        "/api/v1/auth/login",
        json={"email": "tenant_theme_2@example.com", "password": "SecurePassword123!"},
    )
    cookies_2 = login_2.cookies

    # User 1 sets dark mode
    client.put(
        "/api/v1/integrations/preferences",
        json={"theme_preference": "dark"},
        cookies=cookies_1,
    )

    # User 2 should still have system mode
    res_2 = client.get("/api/v1/integrations/preferences", cookies=cookies_2)
    assert res_2.status_code == 200
    assert res_2.json()["theme_preference"] == "system"

