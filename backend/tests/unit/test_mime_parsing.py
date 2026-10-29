"""
Unit tests for MIME message parsing and attachment metadata extraction.
"""
import base64
from app.services.gmail_service import _walk_mime_parts


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")


def test_walk_mime_parts_plain_and_html():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"data": b64("Plain text content")},
            },
            {
                "mimeType": "text/html",
                "body": {"data": b64("<p>HTML content</p>")},
            },
        ],
    }

    plain, html, attachments = _walk_mime_parts(payload)
    assert "Plain text content" in plain
    assert "<p>HTML content</p>" in html
    assert len(attachments) == 0


def test_walk_mime_parts_nested_multipart_and_attachments():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": b64("Nested body text")},
                    }
                ],
            },
            {
                "mimeType": "application/pdf",
                "filename": "syllabus_fall2026.pdf",
                "body": {"size": 204800, "attachmentId": "att_12345"},
            },
            {
                "mimeType": "image/png",
                "filename": "chart.png",
                "body": {"size": 51200, "attachmentId": "att_67890"},
            },
        ],
    }

    plain, html, attachments = _walk_mime_parts(payload)
    assert "Nested body text" in plain
    assert len(attachments) == 2
    assert attachments[0]["filename"] == "syllabus_fall2026.pdf"
    assert attachments[0]["mime_type"] == "application/pdf"
    assert attachments[0]["size"] == 204800
    assert attachments[1]["filename"] == "chart.png"
    assert attachments[1]["size"] == 51200

