"""Regression tests for Round 3 security findings."""
from datetime import datetime, timezone
import base64
import hashlib
import hmac
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.api.v1.notifications import send_test_notification
from app.schemas.notifications import NotificationTestRequest
from app.services.billing import CashfreeAdapter
from app.config import settings


def test_notification_test_rejects_unowned_explicit_destination(monkeypatch):
    """An explicit destination_id must never bypass the caller ownership check."""
    db = SimpleNamespace(
        destinations=Mock(),
        notification_deliveries=Mock(),
    )
    db.destinations.find_one.return_value = None
    current_user = SimpleNamespace(id="user-a")
    deliver = Mock(return_value=(True, None))
    monkeypatch.setattr(
        "app.api.v1.notifications.deliver_notification_idempotent", deliver
    )

    payload = NotificationTestRequest(
        channel="telegram",
        destination_id="987654321",
        message="unauthorized test",
    )
    with pytest.raises(HTTPException) as exc:
        send_test_notification(payload, current_user=current_user, db=db)

    assert exc.value.status_code == 404
    deliver.assert_not_called()
    db.destinations.find_one.assert_called_once_with({
        "user_id": "user-a",
        "type": "telegram",
        "target_id": "987654321",
    })


def test_notification_test_resolves_only_owned_default_destination(monkeypatch):
    """A registered destination owned by the current user remains usable."""
    db = SimpleNamespace(
        destinations=Mock(),
        notification_deliveries=Mock(),
    )
    db.destinations.find_one.side_effect = [
        {"target_id": "123456789", "user_id": "user-a", "type": "telegram"},
        {"target_id": "123456789", "user_id": "user-a", "type": "telegram"},
    ]
    db.notification_deliveries.count_documents.return_value = 0
    current_user = SimpleNamespace(id="user-a")
    deliver = Mock(return_value=(True, None))
    monkeypatch.setattr(
        "app.api.v1.notifications.deliver_notification_idempotent", deliver
    )

    response = send_test_notification(
        NotificationTestRequest(channel="telegram"),
        current_user=current_user,
        db=db,
    )

    assert response["status"] == "sent"
    deliver.assert_called_once()


def test_cashfree_webhook_rejects_stale_signed_timestamp(monkeypatch):
    """A valid HMAC with an old timestamp must be rejected as a replay."""
    secret = "round3-test-webhook-secret"
    monkeypatch.setattr(settings, "cashfree_webhook_secret", secret)
    body = b'{"data":{"link_status":"PAID"}}'
    stale_timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000) - 600_000)
    signature = base64.b64encode(
        hmac.new(secret.encode(), stale_timestamp.encode() + body, hashlib.sha256).digest()
    ).decode()

    assert not CashfreeAdapter().verify_webhook(
        body,
        {
            "x-webhook-timestamp": stale_timestamp,
            "x-webhook-signature": signature,
        },
    )


def test_cashfree_webhook_accepts_fresh_signed_timestamp(monkeypatch):
    """A fresh timestamp with the correct HMAC remains accepted."""
    secret = "round3-test-webhook-secret"
    monkeypatch.setattr(settings, "cashfree_webhook_secret", secret)
    body = b'{"data":{"link_status":"PAID"}}'
    timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    signature = base64.b64encode(
        hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256).digest()
    ).decode()

    assert CashfreeAdapter().verify_webhook(
        body,
        {
            "x-webhook-timestamp": timestamp,
            "x-webhook-signature": signature,
        },
    )


def test_scheduler_does_not_claim_ownerless_mailbox_by_email(monkeypatch):
    """An orphaned mailbox is quarantined, even when its email matches a user."""
    from app.services import scheduler

    db = SimpleNamespace(
        accounts=SimpleNamespace(
            find=lambda query: [
                {
                    "email": "user-a@example.com",
                    "user_id": None,
                    "token_path": "/tmp/legacy-token.json",
                    "active": True,
                }
            ]
        )
    )
    billing_session = Mock()
    monkeypatch.setattr(
        "app.database.session.SessionLocal", lambda: billing_session
    )
    sync = Mock()
    monkeypatch.setattr(scheduler, "sync_messages_incremental", sync)

    scheduler._poll_all_accounts(
        db, user_id="user-a", user_email="user-a@example.com"
    )

    sync.assert_not_called()
    billing_session.close.assert_called_once()


def test_bridge_webhook_configuration_fails_closed_and_binds_loopback():
    """Guard bridge network exposure and unsafe webhook defaults."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    source = (repo_root / "whatsapp-bridge" / "src" / "index.js").read_text(
        encoding="utf-8"
    )

    assert 'app.listen(PORT, "127.0.0.1"' in source
    assert 'savedConfig.verifyToken || ""' in source
    assert '"change-me-webhook"' not in source.split("function startMeta()", 1)[1].split(
        "function ", 1
    )[0]
    assert 'app.post("/api/configure", requireAuth' in source
    assert 'metaConfig.verifyToken = verifyToken;' in source
    assert 'WHATSAPP_APP_SECRET' in source
    assert 'x-hub-signature-256' in source
    assert 'crypto.timingSafeEqual(supplied, expected)' in source
    assert 'msg.text?.body' not in source
