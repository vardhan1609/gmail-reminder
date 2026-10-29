"""
Robust Gmail API connector supporting OAuth 2.0, token encryption at rest,
recursive MIME parsing, attachment metadata extraction (name, mime_type, size),
history API incremental sync, pagination with nextPageToken, label filtering,
and fault-tolerant error handling (404 deleted messages, 429 quota, expired history ID).
"""
import base64
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings
from app.utils.crypto import save_secure_token, load_secure_token
from app.utils.logger import get_logger

logger = get_logger(__name__)

SCOPES = [s for s in settings.gmail_scopes.split() if s]
TOKENS_DIR = settings.resolved_tokens_dir
TOKENS_DIR.mkdir(parents=True, exist_ok=True)


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


def build_auth_url(state: Optional[str] = None) -> Tuple[str, str]:
    """Generates the OAuth consent URL and CSRF state parameter."""
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = settings.google_redirect_uri
    auth_url, generated_state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return auth_url, generated_state


def exchange_code_for_token(code: str) -> Tuple[str, str]:
    """
    Exchanges authorization code for credentials, saves them securely
    with encryption at rest, and returns (email_address, token_path).
    """
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = settings.google_redirect_uri
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Discover account email
    svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
    profile = svc.users().getProfile(userId="me").execute()
    email_address = profile.get("emailAddress", "unknown@gmail.com")

    token_path = TOKENS_DIR / f"gmail_{uuid.uuid4().hex[:8]}.json"
    save_secure_token(token_path, creds.to_json())
    logger.info("Saved encrypted Gmail credentials for %s", email_address)
    return email_address, str(token_path)


def _load_credentials(token_path: str) -> Optional[Credentials]:
    path = Path(token_path)
    if not path.exists():
        return None
    raw_json = load_secure_token(path)
    if not raw_json:
        return None
    try:
        data = json.loads(raw_json)
        creds = Credentials.from_authorized_user_info(data, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_secure_token(path, creds.to_json())
            logger.info("Refreshed access token for %s", path.name)
        return creds
    except Exception as exc:
        logger.error("Failed to load or refresh credentials: %s", exc)
        return None


def is_authenticated(token_path: str) -> bool:
    creds = _load_credentials(token_path)
    return bool(creds and creds.valid)


def get_credentials(token_path: str) -> Credentials:
    creds = _load_credentials(token_path)
    if not creds:
        raise RuntimeError(f"No valid credentials found at {token_path}")
    return creds


def _service(token_path: str):
    creds = get_credentials(token_path)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_current_history_id(token_path: str) -> Optional[str]:
    """Retrieves current mailbox historyId."""
    try:
        svc = _service(token_path)
        profile = svc.users().getProfile(userId="me").execute()
        return profile.get("historyId")
    except Exception as exc:
        logger.warning("Could not fetch mailbox profile: %s", exc)
        return None


def build_search_query(start_date: Optional[datetime] = None) -> str:
    """Builds query based on settings, historical sync days, and label rules."""
    query_parts = []
    if settings.gmail_query:
        query_parts.append(settings.gmail_query)

    if start_date:
        query_parts.append(f"after:{start_date.strftime('%Y/%m/%d')}")
    elif settings.historical_sync_days > 0 and not settings.gmail_query:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.historical_sync_days)
        query_parts.append(f"after:{cutoff.strftime('%Y/%m/%d')}")

    # Label exclusions if configured
    excluded = settings.excluded_labels
    for label in excluded:
        query_parts.append(f"-label:{label.lower()}")

    return " ".join(query_parts).strip()


def list_messages_paginated(
    token_path: str, query: Optional[str] = None, max_pages: int = 5, page_size: int = 50
) -> List[str]:
    """
    Lists message IDs matching query with full pagination support using nextPageToken.
    Safely respects API quotas and max_pages limits.
    """
    svc = _service(token_path)
    q = query if query is not None else build_search_query()
    message_ids: List[str] = []
    page_token = None
    pages_fetched = 0

    while pages_fetched < max_pages:
        try:
            req = svc.users().messages().list(
                userId="me",
                q=q,
                maxResults=page_size,
                pageToken=page_token,
            )
            resp = req.execute()
            messages = resp.get("messages", [])
            for m in messages:
                if m.get("id"):
                    message_ids.append(m["id"])

            page_token = resp.get("nextPageToken")
            pages_fetched += 1
            if not page_token:
                break
        except HttpError as exc:
            if exc.resp.status in (429, 503):
                logger.warning("Gmail API rate limit/quota reached: %s", exc)
                break
            logger.error("Gmail messages.list failed: %s", exc)
            raise

    return message_ids


def sync_messages_incremental(
    token_path: str, start_history_id: Optional[str]
) -> Tuple[List[str], Optional[str]]:
    """
    Synchronizes new messages using Gmail History API.
    If historyId is expired (404/400), gracefully catches it and returns empty list with current historyId
    so caller can perform a standard query fallback.
    """
    if not start_history_id:
        curr_id = get_current_history_id(token_path)
        msg_ids = list_messages_paginated(token_path)
        return msg_ids, curr_id

    svc = _service(token_path)
    try:
        new_message_ids: List[str] = []
        page_token = None
        new_history_id = start_history_id

        while True:
            resp = svc.users().history().list(
                userId="me",
                startHistoryId=start_history_id,
                historyTypes=["messageAdded"],
                pageToken=page_token,
                maxResults=100,
            ).execute()

            new_history_id = resp.get("historyId", new_history_id)
            history_records = resp.get("history", [])
            for record in history_records:
                for msg_added in record.get("messagesAdded", []):
                    msg = msg_added.get("message")
                    if msg and msg.get("id"):
                        new_message_ids.append(msg["id"])

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        return list(dict.fromkeys(new_message_ids)), new_history_id

    except HttpError as exc:
        if exc.resp.status in (404, 400):
            # Expired history ID
            logger.warning("Gmail historyId %s is expired or invalid. Falling back to query sync.", start_history_id)
            latest_id = get_current_history_id(token_path)
            fallback_msgs = list_messages_paginated(token_path)
            return fallback_msgs, latest_id
        raise


def _walk_mime_parts(part: dict) -> Tuple[str, str, List[Dict[str, Any]]]:
    """
    Recursively walks MIME payload parts extracting:
    - plain text
    - html
    - attachment metadata: {filename, mime_type, size}
    """
    plain, html = "", ""
    attachments: List[Dict[str, Any]] = []

    def decode(data: str) -> str:
        try:
            return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")
        except Exception:
            return ""

    def recurse(p: dict):
        nonlocal plain, html, attachments
        mime = p.get("mimeType", "").lower()
        body = p.get("body", {})
        filename = p.get("filename", "")

        # Check for attachment
        if filename:
            attachments.append({
                "filename": filename,
                "mime_type": mime,
                "size": body.get("size", 0),
                "attachment_id": body.get("attachmentId"),
            })
        elif mime == "text/plain" and body.get("data"):
            plain += decode(body["data"])
        elif mime == "text/html" and body.get("data"):
            html += decode(body["data"])

        for subpart in p.get("parts", []) or []:
            recurse(subpart)

    recurse(part)
    return plain, html, attachments


def get_message(token_path: str, message_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches full message details with error handling for deleted messages (404).
    Extracts headers, plain text, HTML, attachment metadata, labels, and thread ID.
    """
    svc = _service(token_path)
    try:
        msg = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    except HttpError as exc:
        if exc.resp.status == 404:
            logger.info("Message %s was deleted or not found on server", message_id)
            return None
        logger.error("Failed to fetch message %s: %s", message_id, exc)
        raise

    payload = msg.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

    plain, html, attachments = _walk_mime_parts(payload)

    # Parse received timestamp
    received_date = None
    if headers.get("date"):
        try:
            from dateutil import parser as dtparser
            parsed_dt = dtparser.parse(headers["date"])
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
            received_date = parsed_dt
        except Exception:
            received_date = datetime.now(timezone.utc)

    # Extract labels
    label_ids = msg.get("labelIds", [])

    return {
        "gmail_message_id": message_id,
        "gmail_id": message_id,
        "gmail_thread_id": msg.get("threadId"),
        "sender": headers.get("from", "unknown"),
        "recipients": headers.get("to", ""),
        "subject": headers.get("subject", "(no subject)"),
        "received_at": received_date,
        "plain_text": plain,
        "html": html,
        "attachments": attachments,
        "labels": label_ids,
        "snippet": msg.get("snippet", ""),
    }
