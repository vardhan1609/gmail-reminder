"""
Integration tests for system recovery and pending reminders recovery after restart.
"""
from datetime import datetime, timezone, timedelta
from app.database.db import get_db
from app.models.reminder import ReminderStatus
from app.services.scheduler import dispatch_due_reminders


def test_pending_reminders_recovered_after_restart(monkeypatch):
    db = get_db()
    # 1. Seed database with pending reminders (simulating pre-restart state)
    dest = db.destinations.insert_one({
        "type": "telegram",
        "name": "Dev Group",
        "target_id": "11223344",
        "is_default": True,
        "active": True,
    })

    past_due = datetime.now(timezone.utc) - timedelta(minutes=10)
    r1 = db.reminders.insert_one({
        "email_id": "em_restart_1",
        "destination_id": str(dest["id"]),
        "message": "Assignment 1 Reminder",
        "scheduled_at": past_due,
        "status": ReminderStatus.pending.value,
        "retry_count": 0,
    })

    # 2. Mock delivery
    sent_messages = []
    def mock_deliver(email_id, channel, destination_id, notification_type, message, idempotency_key):
        sent_messages.append(message)
        return True, None

    monkeypatch.setattr("app.services.scheduler.deliver_notification_idempotent", mock_deliver)

    # 3. Simulate scheduler dispatch cycle on restart
    dispatched_count = dispatch_due_reminders(db)
    assert dispatched_count == 1
    assert len(sent_messages) == 1

    # 4. Verify reminder status updated to sent
    rec = db.reminders.find_one({"id": str(r1["id"])})
    assert rec["status"] == ReminderStatus.sent.value
    assert rec["sent_at"] is not None

