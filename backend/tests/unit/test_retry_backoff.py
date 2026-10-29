"""
Unit tests for reminder retry logic, exponential backoff, and max retries limit.
"""
from datetime import datetime, timezone, timedelta
from app.database.db import get_db
from app.models.reminder import ReminderStatus
from app.services.scheduler import dispatch_due_reminders


def test_reminder_exponential_backoff_and_failure(monkeypatch):
    db = get_db()
    # Create test destination
    dest = db.destinations.insert_one({
        "type": "telegram",
        "name": "Test Group",
        "target_id": "12345678",
        "is_default": True,
        "active": True,
    })

    # Mock send failure
    def mock_deliver(*args, **kwargs):
        return False, "Temporary network timeout"

    monkeypatch.setattr("app.services.scheduler.deliver_notification_idempotent", mock_deliver)

    # Insert a due reminder
    now = datetime.now(timezone.utc)
    reminder = db.reminders.insert_one({
        "email_id": "em_test_backoff",
        "destination_id": str(dest["id"]),
        "message": "Due assignment",
        "scheduled_at": now - timedelta(minutes=5),
        "status": ReminderStatus.pending.value,
        "retry_count": 0,
    })
    rem_id = str(reminder["id"])

    # Attempt 1: fails, status remains pending, retry_count becomes 1, scheduled_at backed off
    dispatch_due_reminders(db)
    r1 = db.reminders.find_one({"id": rem_id})
    assert r1["retry_count"] == 1
    assert r1["status"] == ReminderStatus.pending.value
    r1_scheduled = datetime.fromisoformat(r1["scheduled_at"]) if isinstance(r1["scheduled_at"], str) else r1["scheduled_at"]
    if r1_scheduled.tzinfo is None:
        r1_scheduled = r1_scheduled.replace(tzinfo=timezone.utc)
    assert r1_scheduled > now

    # Reset scheduled_at to due for next attempts
    db.reminders.update_one({"id": rem_id}, {"$set": {"scheduled_at": now - timedelta(minutes=1), "retry_count": 2}})

    # Attempt 3: fails and reaches maximum retries (>= 3) -> marked as failed
    dispatch_due_reminders(db)
    r3 = db.reminders.find_one({"id": rem_id})
    assert r3["retry_count"] == 3
    assert r3["status"] == ReminderStatus.failed.value
