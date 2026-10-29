"""
Integration tests for Telegram bot adapter, command handling, and error handling.
"""
from unittest.mock import MagicMock
import pytest
from app.config import settings
from app.services.telegram import send_group_message, handle_bot_command, TelegramSendError


def test_telegram_commands():
    start_resp = handle_bot_command("/start", "123456")
    assert "Welcome to Gmail Reminder Bot" in start_resp

    help_resp = handle_bot_command("/help", "123456")
    assert "/start" in help_resp
    assert "Group Setup Guide" in help_resp

    test_resp = handle_bot_command("/test", "123456")
    assert "Test Notification Successful" in test_resp


def test_telegram_send_success(monkeypatch):
    settings.dry_run = False
    settings.telegram_bot_token = "mock_bot_token"
    mock_post = MagicMock()
    mock_post.return_value.status_code = 200
    mock_post.return_value.raise_for_status = MagicMock()
    monkeypatch.setattr("httpx.post", mock_post)

    result = send_group_message("-100987654321", "Test notification to Telegram")
    assert result is True


def test_telegram_invalid_chat_id():
    settings.dry_run = False
    with pytest.raises(TelegramSendError) as exc_info:
        send_group_message("not_a_valid_id", "Test message")
    assert "invalid" in str(exc_info.value).lower()

