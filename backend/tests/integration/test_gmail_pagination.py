"""
Integration tests for Gmail API pagination using nextPageToken.
"""
from unittest.mock import MagicMock
from app.services.gmail_service import list_messages_paginated


def test_gmail_pagination_multiple_pages(monkeypatch):
    mock_svc = MagicMock()
    page1 = {"messages": [{"id": "m1"}, {"id": "m2"}], "nextPageToken": "token_page_2"}
    page2 = {"messages": [{"id": "m3"}, {"id": "m4"}], "nextPageToken": None}

    def mock_list(userId, q, maxResults, pageToken=None):
        req = MagicMock()
        if pageToken == "token_page_2":
            req.execute.return_value = page2
        else:
            req.execute.return_value = page1
        return req

    mock_svc.users().messages().list.side_effect = mock_list
    monkeypatch.setattr("app.services.gmail_service._service", lambda tp: mock_svc)

    ids = list_messages_paginated("dummy_token.json", max_pages=3)
    assert ids == ["m1", "m2", "m3", "m4"]

