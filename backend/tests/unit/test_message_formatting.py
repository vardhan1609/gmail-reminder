"""
Unit tests for message formatting, length truncation, and privacy mode.
"""
from app.services.notifier import format_email_notification, format_digest_summary
from app.services.whatsapp import format_whatsapp_message, MAX_WA_MESSAGE_LENGTH
from app.services.telegram import format_telegram_message, escape_markdown_v2, MAX_TELEGRAM_MESSAGE_LENGTH


def test_format_email_notification_normal():
    data = {
        "gmail_message_id": "msg_123",
        "sender": "bursar@university.edu",
        "subject": "Tuition Due",
        "category": "Fees and payments",
        "plain_body": "Please pay by next week.",
    }
    formatted = format_email_notification(data, privacy_mode=False)
    assert "*From:* bursar@university.edu" in formatted
    assert "*Subject:* Tuition Due" in formatted
    assert "https://mail.google.com/mail/u/0/#inbox/msg_123" in formatted
    assert "Please pay by next week." in formatted


def test_format_email_notification_privacy_mode():
    data = {
        "gmail_message_id": "msg_123",
        "sender": "doctor@hospital.edu",
        "subject": "Confidential Medical Test Result",
        "category": "Personal messages",
        "plain_body": "Extremely private diagnostic report content.",
    }
    formatted = format_email_notification(data, privacy_mode=True)
    assert "*From:* doctor@hospital.edu" in formatted
    assert "*Subject:* Confidential Medical Test Result" in formatted
    # Crucial: body text must be omitted in privacy mode
    assert "diagnostic report content" not in formatted
    assert "Open in Gmail" in formatted


def test_format_digest_summary():
    emails = [
        {"subject": "Exam schedule", "sender": "registrar@uni.edu", "category": "Examinations and results"},
        {"subject": "Lab 3 Due", "sender": "ta@uni.edu", "category": "Academics and assignments"},
    ]
    summary = format_digest_summary(emails)
    assert "2 new messages" in summary
    assert "Exam schedule" in summary
    assert "Lab 3 Due" in summary


def test_whatsapp_length_truncation():
    giant_text = "A" * (MAX_WA_MESSAGE_LENGTH + 500)
    truncated = format_whatsapp_message(giant_text)
    assert len(truncated) <= MAX_WA_MESSAGE_LENGTH
    assert "[truncated]" in truncated


def test_telegram_length_truncation():
    giant_text = "B" * (MAX_TELEGRAM_MESSAGE_LENGTH + 500)
    truncated = format_telegram_message(giant_text)
    assert len(truncated) <= MAX_TELEGRAM_MESSAGE_LENGTH
    assert "[truncated]" in truncated

