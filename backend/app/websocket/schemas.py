"""
WebSocket event schemas, enums, envelopes, and payload validation.
Enforces strict boundary isolation: no passwords, tokens, full bodies, or sensitive credentials
are ever permitted in WebSocket payloads.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class EventType(str, enum.Enum):
    CONNECTION_ESTABLISHED = "connection.established"
    EMAIL_RECEIVED = "email.received"
    EMAIL_CLASSIFIED = "email.classified"
    REMINDER_CREATED = "reminder.created"
    REMINDER_UPDATED = "reminder.updated"
    REMINDER_DUE_SOON = "reminder.due_soon"
    NOTIFICATION_QUEUED = "notification.queued"
    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_FAILED = "notification.failed"
    GMAIL_SYNC_STARTED = "gmail.sync.started"
    GMAIL_SYNC_COMPLETED = "gmail.sync.completed"
    GMAIL_SYNC_FAILED = "gmail.sync.failed"
    SYSTEM_ERROR = "system.error"


# Explicit denylist of sensitive field names that must never be emitted over WebSocket
SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "token",
    "token_hash",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "mfa_secret",
    "recovery_code",
    "plain_body",
    "body",
    "html_body",
    "attachments_meta",
    "session_token_hash",
    "session_id",
}


def sanitize_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively removes sensitive keys and values from data dictionaries."""
    sanitized: Dict[str, Any] = {}
    for k, v in data.items():
        key_lower = k.lower()
        if any(s in key_lower for s in SENSITIVE_KEYS):
            continue
        if isinstance(v, dict):
            sanitized[k] = sanitize_payload(v)
        elif isinstance(v, list):
            sanitized[k] = [
                sanitize_payload(item) if isinstance(item, dict) else item
                for item in v
            ]
        elif isinstance(v, datetime):
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            sanitized[k] = v.astimezone(timezone.utc).isoformat()
        else:
            sanitized[k] = v
    return sanitized


class WebSocketEnvelope(BaseModel):
    """Standardized JSON envelope for all server-to-client WebSocket events."""
    event: str
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    data: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("data", mode="before")
    @classmethod
    def strip_sensitive_data(cls, v: Any) -> Dict[str, Any]:
        if isinstance(v, dict):
            return sanitize_payload(v)
        return {}


# ─── Individual Payload Models for Schema Validation ───

class ConnectionEstablishedData(BaseModel):
    user_id: str
    connection_id: str
    connected_at: str
    heartbeat_interval_seconds: int = 30
    supported_events: List[str] = [e.value for e in EventType]


class EmailReceivedData(BaseModel):
    email_id: str
    subject: str
    sender: str
    category: Optional[str] = None
    received_at: str
    has_deadline: bool = False


class EmailClassifiedData(BaseModel):
    email_id: str
    category: str
    confidence_score: float
    extracted_deadline: Optional[str] = None


class ReminderCreatedData(BaseModel):
    reminder_id: str
    email_id: str
    scheduled_at: str
    message_preview: Optional[str] = None
    status: str = "pending"


class ReminderUpdatedData(BaseModel):
    reminder_id: str
    email_id: Optional[str] = None
    scheduled_at: Optional[str] = None
    status: str
    retry_count: int = 0
    last_error: Optional[str] = None


class ReminderDueSoonData(BaseModel):
    reminder_id: str
    email_id: Optional[str] = None
    scheduled_at: str
    minutes_remaining: int


class NotificationQueuedData(BaseModel):
    notification_id: str
    email_id: Optional[str] = None
    channel: str
    notification_type: str


class NotificationSentData(BaseModel):
    notification_id: str
    email_id: Optional[str] = None
    channel: str
    sent_at: str


class NotificationFailedData(BaseModel):
    notification_id: str
    email_id: Optional[str] = None
    channel: str
    error: str


class GmailSyncStartedData(BaseModel):
    account_id: str
    email: str
    started_at: str


class GmailSyncCompletedData(BaseModel):
    account_id: str
    email: str
    new_messages_count: int
    completed_at: str


class GmailSyncFailedData(BaseModel):
    account_id: str
    email: str
    error: str
    failed_at: str


class SystemErrorData(BaseModel):
    error_code: str
    message: str
    timestamp: str

