"""
Integration tests for API authentication and authorization controls.
"""
from fastapi.testclient import TestClient


def test_api_v1_endpoints_require_auth(client: TestClient):
    # Requesting protected endpoint without X-API-Key should return 401
    resp = client.get("/api/v1/emails")
    assert resp.status_code == 401
    assert "unauthorized" in resp.text.lower()


def test_api_v1_endpoints_succeed_with_valid_auth(client: TestClient, auth_headers):
    # Requesting with valid X-API-Key should return 200
    resp = client.get("/api/v1/emails", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "emails" in data
    assert "total" in data


def test_public_health_and_ready_endpoints(client: TestClient):
    # /health and /ready must remain publicly accessible without auth
    h_resp = client.get("/health")
    assert h_resp.status_code == 200
    assert h_resp.json()["status"] == "ok"

    r_resp = client.get("/ready")
    assert r_resp.status_code in (200, 503)

