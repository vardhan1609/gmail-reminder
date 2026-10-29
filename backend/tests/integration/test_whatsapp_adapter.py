"""
Integration tests for WhatsApp adapter: dry-run, bridge calls, and error handling.
"""
from unittest.mock import MagicMock
import pytest
from app.config import settings
from app.services.whatsapp import send_group_message, WhatsAppSendError


def test_whatsapp_dry_run_mode():
    settings.dry_run = True
    result = send_group_message("120363012345@g.us", "Test message in dry run mode")
    assert result is True


def test_whatsapp_bridge_call(monkeypatch):
    settings.dry_run = False
    mock_post = MagicMock()
    mock_post.return_value.status_code = 200
    mock_post.return_value.raise_for_status = MagicMock()
    monkeypatch.setattr("httpx.post", mock_post)

    result = send_group_message("120363012345@g.us", "Normal bridge notification")
    assert result is True
    assert mock_post.called
    call_args = mock_post.call_args
    assert call_args[1]["json"]["groupId"] == "120363012345@g.us"


def test_whatsapp_rate_limit_handling(monkeypatch):
    settings.dry_run = False
    mock_post = MagicMock()
    mock_post.return_value.status_code = 429
    monkeypatch.setattr("httpx.post", mock_post)

    with pytest.raises(WhatsAppSendError) as exc_info:
        send_group_message("120363012345@g.us", "Rate limit test")
    assert "rate limit" in str(exc_info.value).lower()

