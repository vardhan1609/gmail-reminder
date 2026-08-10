"""
Wraps Google OAuth2 + the Gmail REST API. Supports multiple connected
mailboxes: each Account row (app/models/account.py) has its own token file
under TOKENS_DIR, so polling/reading is always scoped to one account at a
time by passing its `token_path`.

Flow to connect a new mailbox:
  1. GET /accounts/gmail/login             -> redirect to Google consent
  2. GET /accounts/gmail/callback          -> exchange code, discover the
                                               mailbox's own address, create
                                               (or reuse) tokens/gmail_<n>.json,
                                               upsert an Account row.
  3. app/services/scheduler.py polls every active Account's mailbox.
"""
import base64
import uuid
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

SCOPES = settings.gmail_scopes.split()
TOKENS_DIR = settings.resolved_tokens_dir
TOKENS_DIR.mkdir(exist_ok=True)


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def build_auth_url() -> str:
    """Starts a new-mailbox connection flow. Returns the consent screen URL."""
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = settings.google_redirect_uri
    auth_url, _state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # forces refresh_token to be returned every time
    )
    return auth_url


def exchange_code_for_token(code: str) -> tuple[str, str]:
    """
    Exchanges an OAuth code for tokens, saves them to a fresh per-account
    token file, and returns (mailbox_email_address, token_path) so the
    caller can upsert an Account row.
    """
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = settings.google_redirect_uri
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Discover which mailbox we just got access to (needed because the same
    # app credentials are shared across every connected account).
    svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
    profile = svc.users().getProfile(userId="me").execute()
    email_address = profile["emailAddress"]

    token_path = TOKENS_DIR / f"gmail_{uuid.uuid4().hex[:8]}.json"
    token_path.write_text(creds.to_json())
    logger.info("Connected Gmail mailbox %s -> %s", email_address, token_path)
    return email_address, str(token_path)


def _load_credentials(token_path: str) -> Optional[Credentials]:
    path = Path(token_path)
    if not path.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json())
        logger.info("Refreshed Gmail access token for %s", token_path)
    return creds


def is_authenticated(token_path: str) -> bool:
    creds = _load_credentials(token_path)
    return bool(creds and creds.valid)


def get_credentials(token_path: str) -> Credentials:
    """Exposed so other services (e.g. Google Calendar) can reuse the same
    per-account OAuth token without a second consent screen."""
    creds = _load_credentials(token_path)
    if not creds:
        raise RuntimeError(f"No valid credentials at {token_path}")
    return creds


def _service(token_path: str):
    creds = get_credentials(token_path)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def list_new_message_ids(token_path: str, query: Optional[str] = None) -> list[str]:
    """Return raw Gmail message IDs matching the configured search query, for one mailbox."""
    svc = _service(token_path)
    query = query or settings.gmail_query
    result = svc.users().messages().list(userId="me", q=query, maxResults=25).execute()
    messages = result.get("messages", [])
    return [m["id"] for m in messages]


def _walk_parts(payload: dict) -> tuple[str, str]:
    """Recursively extract (plain_text, html) bodies from a Gmail payload."""
    plain, html = "", ""

    def decode(data: str) -> str:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")

    def walk(part: dict):
        nonlocal plain, html
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        if mime == "text/plain" and body.get("data"):
            plain += decode(body["data"])
        elif mime == "text/html" and body.get("data"):
            html += decode(body["data"])
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    return plain, html


def get_message(token_path: str, message_id: str) -> dict:
    """Fetch a single message from one mailbox and normalize it into a plain dict."""
    svc = _service(token_path)
    msg = svc.users().messages().get(userId="me", id=message_id, format="full").execute()

    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
    plain, html = _walk_parts(msg["payload"])

    attachments = []
    for part in msg["payload"].get("parts", []) or []:
        filename = part.get("filename")
        if filename:
            attachments.append(
                {
                    "filename": filename,
                    "mime_type": part.get("mimeType"),
                    "attachment_id": part.get("body", {}).get("attachmentId"),
                }
            )

    return {
        "gmail_id": message_id,
        "sender": headers.get("from", "unknown"),
        "subject": headers.get("subject", "(no subject)"),
        "date": headers.get("date"),
        "plain_text": plain,
        "html": html,
        "attachments": attachments,
        "snippet": msg.get("snippet", ""),
    }
