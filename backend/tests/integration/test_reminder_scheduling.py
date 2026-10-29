"""
Integration tests for deadline reminder creation and multi-offset scheduling.
"""
from datetime import datetime, timezone, timedelta
from app.database.db import get_db
from app.services.scheduler import _process_email


def test_reminder_scheduling_multi_offsets():
    db = get_db()
    # Create default destination
    dest = db.destinations.insert_one({
        "type": "telegram",
        "name": "Class Group",
        "target_id": "-10012345678",
        "is_default": True,
        "active": True,
    })

    future_deadline = datetime.now(timezone.utc) + timedelta(days=3)
    deadline_str = future_deadline.strftime("%d %b %Y at 11:59 PM")

    email_data = {
        "gmail_message_id": "msg_with_deadline_multi",
        "sender": "prof@uni.edu",
        "subject": "Final Project Due Date",
        "plain_text": f"The submission deadline is {deadline_str}. Late submissions strictly prohibited.",
        "received_at": datetime.now(timezone.utc),
    }

    _process_email(db, "acc_1", email_data)

    email_rec = db.emails.find_one({"gmail_message_id": "msg_with_deadline_multi"})
    assert email_rec is not None
    assert email_rec["extracted_deadline"] is not None

    # Check reminders created for offsets (24h, 6h, 1h)
    reminders = list(db.reminders.find({"email_id": str(email_rec["id"])}))
    assert len(reminders) >= 1
    for r in reminders:
        assert r["status"] == "pending"
        assert "Deadline Reminder" in r["message"]

