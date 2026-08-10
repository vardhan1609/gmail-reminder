"""
Single Outlook/Microsoft 365 calendar connection via MSAL + Microsoft
Graph. Unlike Gmail, this isn't per-monitored-mailbox -- it's one shared
calendar (e.g. a personal Outlook account, or a shared department
calendar) that deadline events get pushed to regardless of which Gmail
account the announcement came from. See README for why.

Connect flow:
  1. GET /calendar/outlook/login     -> redirect to Microsoft consent
  2. GET /calendar/outlook/callback  -> exchange code, persist token cache
  3. app/services/scheduler.py calls create_event() for extracted deadlines
     when OUTLOOK connection is active.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
import msal

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

TOKENS_DIR = settings.resolved_tokens_dir
TOKENS_DIR.mkdir(exist_ok=True)
CACHE_PATH = TOKENS_DIR / "outlook_cache.json"
PENDING_FLOW_PATH = TOKENS_DIR / "outlook_pending_flow.json"

AUTHORITY = f"https://login.microsoftonline.com/{settings.outlook_tenant_id}"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if CACHE_PATH.exists():
        cache.deserialize(CACHE_PATH.read_text())
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        CACHE_PATH.write_text(cache.serialize())


def _msal_app(cache: Optional[msal.SerializableTokenCache] = None) -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        client_id=settings.outlook_client_id,
        client_credential=settings.outlook_client_secret,
        authority=AUTHORITY,
        token_cache=cache or _load_cache(),
    )


def build_auth_url() -> str:
    """Starts the Outlook connect flow. The flow's state is persisted to
    disk so /calendar/outlook/callback can complete it (single pending
    connection at a time, which matches the single shared-calendar model)."""
    app_ = _msal_app()
    flow = app_.initiate_auth_code_flow(
        scopes=settings.outlook_scopes.split(),
        redirect_uri=settings.outlook_redirect_uri,
    )
    PENDING_FLOW_PATH.write_text(json.dumps(flow))
    return flow["auth_uri"]


def complete_auth(query_params: dict) -> str:
    """Exchanges the callback query params for tokens. Returns the
    connected account's username/email."""
    if not PENDING_FLOW_PATH.exists():
        raise RuntimeError("No pending Outlook auth flow found; start at /calendar/outlook/login")

    flow = json.loads(PENDING_FLOW_PATH.read_text())
    cache = _load_cache()
    app_ = _msal_app(cache)
    result = app_.acquire_token_by_auth_code_flow(flow, query_params)

    PENDING_FLOW_PATH.unlink(missing_ok=True)

    if "error" in result:
        raise RuntimeError(f"Outlook auth failed: {result.get('error_description', result['error'])}")

    _save_cache(cache)
    username = result.get("id_token_claims", {}).get("preferred_username", "unknown")
    logger.info("Connected Outlook calendar for %s", username)
    return username


def is_connected() -> bool:
    cache = _load_cache()
    app_ = _msal_app(cache)
    return bool(app_.get_accounts())


def _get_access_token() -> str:
    cache = _load_cache()
    app_ = _msal_app(cache)
    accounts = app_.get_accounts()
    if not accounts:
        raise RuntimeError("Outlook calendar not connected. Visit /calendar/outlook/login")

    result = app_.acquire_token_silent(settings.outlook_scopes.split(), account=accounts[0])
    _save_cache(cache)
    if not result or "access_token" not in result:
        raise RuntimeError("Outlook token refresh failed; reconnect via /calendar/outlook/login")
    return result["access_token"]


def create_event(summary: str, description: str, start: datetime, duration_minutes: int = 30) -> str:
    """Creates an event on the connected Outlook calendar. Returns the
    created event's Graph ID (store this to avoid duplicate creation)."""
    token = _get_access_token()
    end = start + timedelta(minutes=duration_minutes)

    body = {
        "subject": summary,
        "body": {"contentType": "Text", "content": description},
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        "isReminderOn": True,
        "reminderMinutesBeforeStart": 60,
    }

    resp = httpx.post(
        f"{GRAPH_BASE}/me/events",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    event = resp.json()
    logger.info("Created Outlook Calendar event %s for %r", event["id"], summary)
    return event["id"]
