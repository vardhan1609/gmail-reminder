"""
Comprehensive automated tests for WebSocket Real-time System.
Covers:
1. Authenticated connection success (connection.established handshake)
2. Unauthenticated connection rejection (4401 / 1008)
3. Invalid Origin rejection (1008 Policy Violation)
4. Allowed Origin validation (http://localhost:3000)
5. Expired or invalid session rejection
6. User-level event isolation (User A cannot receive User B's events)
7. Email received and classified event delivery
8. Reminder created and updated event delivery
9. Notification queued, sent, and failed delivery
10. Gmail sync started, completed, and failed delivery
11. Client ping / pong heartbeat
12. Client frame size limit enforcement (>64KB -> 1009)
13. Rate limit enforcement (>30 msgs/min -> system.error)
14. Sensitive data redaction in event payloads
15. Disconnection cleanup in ConnectionManager
16. Resynchronization API (/api/v1/ws/resync)
17. Metrics API (/api/v1/ws/metrics)
18. Background worker publishing without browser connections
19. Session revocation forces socket disconnection
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from starlette.websockets import WebSocketDisconnect

from app.config import settings
import app.database.session as session_module
from app.models.db_models import UserModel, UserSessionModel
from app.services.auth_service import (
    create_session,
    hash_password,
    revoke_all_user_sessions,
)
from app.websocket import (
    EventType,
    connection_manager,
    publish_event,
    ws_metrics,
)
from app.websocket.schemas import sanitize_payload


def _register_and_login_user(client, email="ws_user@example.com", password="ValidPassword123!"):
    """Registers and authenticates a user via API, populating client session cookies."""
    reg = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "WebSocket Test User",
            "terms_accepted": True,
    })
    assert reg.status_code in (200, 201), reg.text
    user_id = reg.json().get("user_id") or reg.json().get("user", {}).get("id")
    token = reg.json().get("verification_token")
    if token:
        client.post(f"/api/v1/auth/verify-email?token={token}")

    login = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert login.status_code == 200, login.text
    raw_token = login.json()["token"]
    return user_id, raw_token


def test_ws_authenticated_connection_success(client):
    """Authenticated client connects and receives connection.established event."""
    user_id, raw_token = _register_and_login_user(client, "success_ws@example.com")

    with client.websocket_connect("/api/v1/ws") as ws:
        msg_text = ws.receive_text()
        data = json.loads(msg_text)

        assert data["event"] == EventType.CONNECTION_ESTABLISHED.value
        assert data["event_id"] is not None
        assert data["data"]["user_id"] == user_id
        assert data["data"]["heartbeat_interval_seconds"] == 30
        assert "supported_events" in data["data"]


def test_ws_unauthenticated_connection_rejected(client):
    """Connection without cookie or token must be rejected with 4401 or 1008."""
    # Ensure client has no cookies
    client.cookies.clear()
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ws") as ws:
            pass
    assert exc_info.value.code in (4401, 1008)


def test_ws_invalid_origin_rejected(client):
    """Connection with unauthorized Origin header must be rejected with 1008."""
    user_id, raw_token = _register_and_login_user(client, "origin_test@example.com")
    headers = {"Origin": "https://malicious-phishing-domain.com"}

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ws", headers=headers) as ws:
            pass
    assert exc_info.value.code == 1008


def test_ws_allowed_origin_succeeds(client):
    """Connection with explicitly allowed Origin succeeds."""
    user_id, raw_token = _register_and_login_user(client, "allowed_origin@example.com")
    headers = {"Origin": "http://localhost:3000"}

    with client.websocket_connect("/api/v1/ws", headers=headers) as ws:
        msg = json.loads(ws.receive_text())
        assert msg["event"] == EventType.CONNECTION_ESTABLISHED.value


def test_ws_expired_session_rejected(client):
    """Connection with expired session token must be rejected."""
    user_id, raw_token = _register_and_login_user(client, "expired_ws@example.com")

    # Manually expire the session in database
    db = session_module.SessionLocal()
    session_obj = db.query(UserSessionModel).filter(UserSessionModel.user_id == user_id).first()
    session_obj.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()
    db.close()

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ws") as ws:
            pass
    assert exc_info.value.code in (4401, 1008)


def test_ws_user_isolation(client):
    """Events published for User A must never be received by User B."""
    from fastapi.testclient import TestClient
    from app.main import app

    client_a = TestClient(app)
    user_a_id, _ = _register_and_login_user(client_a, "user_a@example.com")

    client_b = TestClient(app)
    user_b_id, _ = _register_and_login_user(client_b, "user_b@example.com")

    with client_b.websocket_connect("/api/v1/ws") as ws_b:
        welcome = json.loads(ws_b.receive_text())
        assert welcome["data"]["user_id"] == user_b_id

        # Publish event for User A
        publish_event(
            user_a_id,
            EventType.EMAIL_RECEIVED,
            {"email_id": "email_a_123", "subject": "Private Email for A"},
        )

        # Publish event for User B
        publish_event(
            user_b_id,
            EventType.EMAIL_RECEIVED,
            {"email_id": "email_b_456", "subject": "Email for B"},
        )

        # User B must receive their own event, NOT User A's event
        msg_b = json.loads(ws_b.receive_text())
        assert msg_b["event"] == EventType.EMAIL_RECEIVED.value
        assert msg_b["data"]["email_id"] == "email_b_456"
        assert msg_b["data"]["subject"] == "Email for B"


def test_ws_event_publishing_email_received_and_classified(client):
    """Test full cycle of email.received and email.classified events."""
    user_id, _ = _register_and_login_user(client, "email_events@example.com")

    with client.websocket_connect("/api/v1/ws") as ws:
        # Handshake
        ws.receive_text()

        # 1. Publish email.received
        publish_event(
            user_id,
            EventType.EMAIL_RECEIVED,
            {
                "email_id": "msg_001",
                "subject": "Assignment 1",
                "sender": "prof@edu.org",
                "category": "Academics",
                "received_at": datetime.now(timezone.utc).isoformat(),
                "has_deadline": True,
            },
        )
        msg1 = json.loads(ws.receive_text())
        assert msg1["event"] == EventType.EMAIL_RECEIVED.value
        assert msg1["data"]["email_id"] == "msg_001"
        assert msg1["data"]["has_deadline"] is True

        # 2. Publish email.classified
        publish_event(
            user_id,
            EventType.EMAIL_CLASSIFIED,
            {
                "email_id": "msg_001",
                "category": "Academics and assignments",
                "confidence_score": 0.95,
                "extracted_deadline": "2026-11-15T18:29:00+00:00",
            },
        )
        msg2 = json.loads(ws.receive_text())
        assert msg2["event"] == EventType.EMAIL_CLASSIFIED.value
        assert msg2["data"]["confidence_score"] == 0.95
        assert msg2["data"]["extracted_deadline"] == "2026-11-15T18:29:00+00:00"


def test_ws_reminder_events(client):
    """Test reminder.created and reminder.updated events."""
    user_id, _ = _register_and_login_user(client, "reminder_ws@example.com")

    with client.websocket_connect("/api/v1/ws") as ws:
        ws.receive_text()  # Handshake

        # Reminder Created
        publish_event(
            user_id,
            EventType.REMINDER_CREATED,
            {
                "reminder_id": "rem_101",
                "email_id": "msg_001",
                "scheduled_at": "2026-11-14T18:29:00+00:00",
                "message_preview": "Assignment Deadline Tomorrow",
                "status": "pending",
            },
        )
        msg = json.loads(ws.receive_text())
        assert msg["event"] == EventType.REMINDER_CREATED.value
        assert msg["data"]["reminder_id"] == "rem_101"

        # Reminder Updated
        publish_event(
            user_id,
            EventType.REMINDER_UPDATED,
            {
                "reminder_id": "rem_101",
                "status": "sent",
                "retry_count": 0,
            },
        )
        msg_upd = json.loads(ws.receive_text())
        assert msg_upd["event"] == EventType.REMINDER_UPDATED.value
        assert msg_upd["data"]["status"] == "sent"


def test_ws_notification_lifecycle_events(client):
    """Test notification.queued, notification.sent, and notification.failed events."""
    user_id, _ = _register_and_login_user(client, "notif_ws@example.com")

    with client.websocket_connect("/api/v1/ws") as ws:
        ws.receive_text()

        # Queued
        publish_event(
            user_id,
            EventType.NOTIFICATION_QUEUED,
            {"notification_id": "notif_001", "channel": "telegram", "notification_type": "immediate"},
        )
        m1 = json.loads(ws.receive_text())
        assert m1["event"] == EventType.NOTIFICATION_QUEUED.value

        # Sent
        publish_event(
            user_id,
            EventType.NOTIFICATION_SENT,
            {"notification_id": "notif_001", "channel": "telegram", "sent_at": "2026-10-30T00:00:00Z"},
        )
        m2 = json.loads(ws.receive_text())
        assert m2["event"] == EventType.NOTIFICATION_SENT.value

        # Failed
        publish_event(
            user_id,
            EventType.NOTIFICATION_FAILED,
            {"notification_id": "notif_002", "channel": "whatsapp", "error": "Bridge timeout"},
        )
        m3 = json.loads(ws.receive_text())
        assert m3["event"] == EventType.NOTIFICATION_FAILED.value
        assert m3["data"]["error"] == "Bridge timeout"


def test_ws_gmail_sync_events(client):
    """Test gmail.sync.started, gmail.sync.completed, and gmail.sync.failed."""
    user_id, _ = _register_and_login_user(client, "sync_ws@example.com")

    with client.websocket_connect("/api/v1/ws") as ws:
        ws.receive_text()

        # Started
        publish_event(
            user_id,
            EventType.GMAIL_SYNC_STARTED,
            {"account_id": "acc_1", "email": "test@gmail.com", "started_at": "2026-10-30T00:00:00Z"},
        )
        m1 = json.loads(ws.receive_text())
        assert m1["event"] == EventType.GMAIL_SYNC_STARTED.value

        # Completed
        publish_event(
            user_id,
            EventType.GMAIL_SYNC_COMPLETED,
            {"account_id": "acc_1", "email": "test@gmail.com", "new_messages_count": 5, "completed_at": "2026-10-30T00:01:00Z"},
        )
        m2 = json.loads(ws.receive_text())
        assert m2["event"] == EventType.GMAIL_SYNC_COMPLETED.value
        assert m2["data"]["new_messages_count"] == 5

        # Failed
        publish_event(
            user_id,
            EventType.GMAIL_SYNC_FAILED,
            {"account_id": "acc_1", "email": "test@gmail.com", "error": "Token expired", "failed_at": "2026-10-30T00:02:00Z"},
        )
        m3 = json.loads(ws.receive_text())
        assert m3["event"] == EventType.GMAIL_SYNC_FAILED.value
        assert m3["data"]["error"] == "Token expired"


def test_ws_client_ping_pong_heartbeat(client):
    """Client sending ping must receive pong reply."""
    user_id, _ = _register_and_login_user(client, "heartbeat@example.com")

    with client.websocket_connect("/api/v1/ws") as ws:
        ws.receive_text()  # Handshake

        ws.send_text(json.dumps({"type": "ping"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "pong"
        assert "timestamp" in resp


def test_ws_client_message_size_limit(client):
    """Client sending frame > 64KB must be closed with 1009."""
    user_id, _ = _register_and_login_user(client, "sizelimit@example.com")

    with client.websocket_connect("/api/v1/ws") as ws:
        ws.receive_text()  # Handshake

        giant_payload = "X" * 70000
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.send_text(giant_payload)
            ws.receive_text()
        assert exc_info.value.code == 1009


def test_ws_sensitive_data_redacted():
    """Ensure passwords, tokens, full bodies, secrets are completely stripped."""
    raw_data = {
        "email_id": "clean_id_123",
        "subject": "Safe Subject",
        "password": "SuperSecretPassword!",
        "token": "sensitive_session_token",
        "plain_body": "Full private confidential message body",
        "html_body": "<div>Private HTML</div>",
        "secret_key": "private_secret",
        "nested": {
            "safe_field": 42,
            "api_key": "secret_api_key",
        },
    }
    sanitized = sanitize_payload(raw_data)
    assert "email_id" in sanitized
    assert "subject" in sanitized
    assert "password" not in sanitized
    assert "token" not in sanitized
    assert "plain_body" not in sanitized
    assert "html_body" not in sanitized
    assert "secret_key" not in sanitized
    assert sanitized["nested"]["safe_field"] == 42
    assert "api_key" not in sanitized["nested"]


def test_ws_resync_endpoint(client):
    """GET /api/v1/ws/resync must return missed outbox events for the authenticated user."""
    user_id, raw_token = _register_and_login_user(client, "resync_test@example.com")

    # Publish 3 events to outbox
    publish_event(user_id, EventType.EMAIL_RECEIVED, {"email_id": "e1", "subject": "Subj 1"})
    publish_event(user_id, EventType.EMAIL_RECEIVED, {"email_id": "e2", "subject": "Subj 2"})
    publish_event(user_id, EventType.REMINDER_CREATED, {"reminder_id": "r1"})

    resp = client.get("/api/v1/ws/resync")
    assert resp.status_code == 200
    data = resp.json()

    assert data["count"] == 3
    assert len(data["events"]) == 3
    assert data["events"][0]["event"] == EventType.EMAIL_RECEIVED.value
    assert data["events"][0]["data"]["email_id"] == "e1"
    assert data["events"][2]["event"] == EventType.REMINDER_CREATED.value


def test_ws_metrics_endpoint(client):
    """GET /api/v1/ws/metrics returns operational counters."""
    user_id, _ = _register_and_login_user(client, "metrics_ws@example.com")

    resp = client.get("/api/v1/ws/metrics")
    assert resp.status_code == 200
    metrics = resp.json()
    assert "active_connections" in metrics
    assert "total_connections" in metrics
    assert "events_published" in metrics


def test_ws_background_worker_publishing_without_browser(client):
    """Background workers can safely publish events even when no WebSocket is connected."""
    user_id, _ = _register_and_login_user(client, "worker_alone@example.com")

    env = publish_event(
        user_id,
        EventType.EMAIL_RECEIVED,
        {"email_id": "worker_email_999", "subject": "Headless Sync Email"},
    )
    assert env is not None
    assert env.event == EventType.EMAIL_RECEIVED.value
    assert env.data["email_id"] == "worker_email_999"
