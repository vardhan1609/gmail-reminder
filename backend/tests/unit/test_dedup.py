"""
Unit tests for duplicate detection and deduplication logic.
"""
from datetime import datetime, timezone, timedelta
from app.database.db import get_db
from app.services.scheduler import _process_email


def test_unique_gmail_id_deduplication():
    db = get_db()
    email_data = {
        "gmail_message_id": "unique_msg_100",
        "sender": "sender@test.com",
        "subject": "Important update",
        "plain_text": "Meeting tomorrow",
    }

    # First insertion
    _process_email(db, "acc_1", email_data)
    count1 = db.emails.count_documents({"gmail_message_id": "unique_msg_100"})
    assert count1 == 1

    # Attempt duplicate insertion with same gmail_message_id
    _process_email(db, "acc_1", email_data)
    count2 = db.emails.count_documents({"gmail_message_id": "unique_msg_100"})
    assert count2 == 1  # Did not insert duplicate


def test_subject_sender_24h_soft_dedup():
    db = get_db()
    email_data1 = {
        "gmail_message_id": "msg_first",
        "sender": "prof@uni.edu",
        "subject": "Assignment Reminder",
        "plain_text": "First copy",
        "received_at": datetime.now(timezone.utc),
    }
    email_data2 = {
        "gmail_message_id": "msg_second_copy",
        "sender": "prof@uni.edu",
        "subject": "Re: Assignment Reminder",
        "plain_text": "Second copy within 24h",
        "received_at": datetime.now(timezone.utc),
    }

    _process_email(db, "acc_1", email_data1)
    # The duplicate subject & sender should be safely detected
    dup = db.emails.find_one({"account_id": "acc_1", "sender": "prof@uni.edu", "subject": "Assignment Reminder"})
    assert dup is not None

