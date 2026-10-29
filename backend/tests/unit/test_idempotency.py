"""
Unit tests for notification delivery idempotency logic.
"""
from app.database.db import get_db
from app.services.notifier import deliver_notification_idempotent


def test_idempotency_prevents_duplicate_sends(monkeypatch):
    send_count = 0

    def mock_send(channel, target, msg):
        nonlocal send_count
        send_count += 1
        return True, None

    monkeypatch.setattr("app.services.notifier.send_to_channel", mock_send)

    key = "idem_key_unique_test_123"
    # 1. First send
    success1, _ = deliver_notification_idempotent(
        email_id="e1",
        channel="telegram",
        destination_id="123456",
        notification_type="immediate",
        message="Hello World",
        idempotency_key=key,
    )
    assert success1 is True
    assert send_count == 1

    # 2. Second send with identical key must NOT invoke send_to_channel again
    success2, _ = deliver_notification_idempotent(
        email_id="e1",
        channel="telegram",
        destination_id="123456",
        notification_type="immediate",
        message="Hello World",
        idempotency_key=key,
    )
    assert success2 is True
    assert send_count == 1  # Remained 1!

