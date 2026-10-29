"""
Integration tests for database models, constraints, and relationships.
"""
from app.database.db import get_db


def test_database_crud_operations():
    db = get_db()
    # Insert Account
    acc = db.accounts.insert_one({
        "email": "test_acc@uni.edu",
        "label": "Test Mailbox",
        "token_path": "tokens/test.json",
        "active": True,
    })
    assert acc["id"] is not None

    # Insert Email
    em = db.emails.insert_one({
        "account_id": str(acc["id"]),
        "gmail_message_id": "crud_msg_001",
        "sender": "sender@uni.edu",
        "subject": "CRUD Test Subject",
        "category": "Academics and assignments",
    })
    assert em["id"] is not None

    # Insert Destination
    dest = db.destinations.insert_one({
        "type": "whatsapp",
        "name": "Study Group",
        "target_id": "120363012345@g.us",
        "is_default": True,
        "active": True,
    })
    assert dest["id"] is not None

    # Insert Reminder
    from datetime import datetime, timezone, timedelta
    rem = db.reminders.insert_one({
        "email_id": str(em["id"]),
        "destination_id": str(dest["id"]),
        "message": "Reminder text",
        "scheduled_at": datetime.now(timezone.utc) + timedelta(hours=2),
        "status": "pending",
        "retry_count": 0,
    })
    assert rem["id"] is not None

    # Query and verify
    found_rem = db.reminders.find_one({"id": str(rem["id"])})
    assert found_rem["status"] == "pending"
    assert found_rem["message"] == "Reminder text"

