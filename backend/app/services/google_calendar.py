"""
Creates deadline events on a connected Gmail account's own Google Calendar.

Reuses the same OAuth token as gmail_service (the connect flow already
requests the `calendar.events` scope alongside `gmail.readonly`), so
enabling this for an account is just flipping Account.calendar_sync_enabled
-- no second consent screen.
"""
from datetime import datetime, timedelta

from googleapiclient.discovery import build

from app.services import gmail_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


def create_event(token_path: str, summary: str, description: str, start: datetime,
                  duration_minutes: int = 30) -> str:
    """Creates a calendar event on the account's primary calendar. Returns
    the created event's ID (store this to avoid duplicate creation)."""
    creds = gmail_service.get_credentials(token_path)
    svc = build("calendar", "v3", credentials=creds, cache_discovery=False)

    end = start + timedelta(minutes=duration_minutes)
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start.isoformat() + "Z", "timeZone": "UTC"},
        "end": {"dateTime": end.isoformat() + "Z", "timeZone": "UTC"},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 24 * 60},
                {"method": "popup", "minutes": 60},
            ],
        },
    }

    created = svc.events().insert(calendarId="primary", body=body).execute()
    logger.info("Created Google Calendar event %s for %r", created["id"], summary)
    return created["id"]
