"""
Integration tests for incremental Gmail History API sync and expired historyId recovery.
"""
from unittest.mock import MagicMock
from googleapiclient.errors import HttpError
import httplib2
from app.services.gmail_service import sync_messages_incremental


def test_gmail_history_sync_success(monkeypatch):
    mock_svc = MagicMock()
    history_resp = {
        "historyId": "99999",
        "history": [
            {
                "messagesAdded": [
                    {"message": {"id": "hist_msg_10"}},
                    {"message": {"id": "hist_msg_20"}},
                ]
            }
        ],
        "nextPageToken": None,
    }
    mock_svc.users().history().list().execute.return_value = history_resp
    monkeypatch.setattr("app.services.gmail_service._service", lambda tp: mock_svc)

    new_ids, new_hist_id = sync_messages_incremental("dummy_token.json", start_history_id="88888")
    assert new_ids == ["hist_msg_10", "hist_msg_20"]
    assert new_hist_id == "99999"


def test_gmail_history_sync_expired_history_fallback(monkeypatch):
    mock_svc = MagicMock()
    # Simulate HTTP 404 on history.list
    resp = httplib2.Response({"status": 404})
    mock_svc.users().history().list().execute.side_effect = HttpError(resp, b"HistoryId not found")

    # Mock profile and list_messages_paginated fallback
    monkeypatch.setattr("app.services.gmail_service._service", lambda tp: mock_svc)
    monkeypatch.setattr("app.services.gmail_service.get_current_history_id", lambda tp: "105000")
    monkeypatch.setattr("app.services.gmail_service.list_messages_paginated", lambda tp: ["fallback_1", "fallback_2"])

    new_ids, new_hist_id = sync_messages_incremental("dummy_token.json", start_history_id="expired_123")
    assert new_ids == ["fallback_1", "fallback_2"]
    assert new_hist_id == "105000"

