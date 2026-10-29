"""
Unit tests for configuration validation and property methods.
"""
from app.config import Settings


def test_config_defaults_and_parsers():
    conf = Settings(
        reminder_offsets_min="60, 120, 1440",
        gmail_include_labels="INBOX, IMPORTANT",
        gmail_exclude_labels="SENT, SPAM, TRASH",
        include_sent=True,
    )
    assert conf.reminder_offsets_minutes == [60, 120, 1440]
    assert conf.included_labels == ["INBOX", "IMPORTANT"]
    # When include_sent is True, SENT should be removed from excluded_labels
    assert "SENT" not in conf.excluded_labels
    assert "SPAM" in conf.excluded_labels
    assert "TRASH" in conf.excluded_labels

