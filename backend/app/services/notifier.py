"""
Central notification dispatcher supporting:
- WhatsApp and Telegram independent delivery
- Immediate notifications, digest summaries, deadline reminders, and test notifications
- Privacy mode (redacting email body and showing only sender/subject/link)
- Idempotency via NotificationDelivery records
- Failure isolation: failure on WhatsApp does NOT block Telegram, and vice-versa
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

from app.config import settings
from app.database.db import get_db
from app.models.notification_delivery import DeliveryChannel, NotificationType, DeliveryStatus
from app.services.telegram import send_group_message as send_tg, bot_is_ready as tg_ready
from app.services.whatsapp import send_group_message as send_wa, bridge_is_ready as wa_ready
from app.utils.logger import get_logger

logger = get_logger(__name__)


def destination_is_ready(dest: Any) -> bool:
    """Checks readiness of specified destination adapter."""
    dtype = getattr(dest, "type", None) or (dest.get("type") if isinstance(dest, dict) else None)
    if dtype in ("whatsapp", "whatsapp_meta"):
        return wa_ready()
    elif dtype == "telegram":
        return tg_ready()
    return False


def build_gmail_link(gmail_message_id: str) -> str:
    return f"https://mail.google.com/mail/u/0/#inbox/{gmail_message_id}"


def format_dual_time_string(
    dt_val: Any,
    email_tz_name: Optional[str] = None,
    tz_offset: Optional[str] = None,
) -> str:
    """Formats datetime with both location/email timezone and UTC."""
    if not dt_val:
        return ""
    if isinstance(dt_val, str):
        try:
            from dateutil import parser as dtparser
            dt = dtparser.parse(dt_val)
        except Exception:
            return dt_val
    elif isinstance(dt_val, datetime):
        dt = dt_val
    else:
        return str(dt_val)

    from datetime import timedelta
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    utc_dt = dt.astimezone(timezone.utc)
    utc_str = utc_dt.strftime("%b %d, %Y, %I:%M %p UTC")

    local_dt = utc_dt
    tz_label = email_tz_name or "Local"
    if tz_offset:
        try:
            hours = int(tz_offset[:3])
            mins = int(tz_offset[0] + tz_offset[3:])
            email_tz = timezone(timedelta(hours=hours, minutes=mins))
            local_dt = utc_dt.astimezone(email_tz)
        except Exception:
            pass

    local_str = local_dt.strftime("%b %d, %Y, %I:%M %p")
    if tz_label and tz_label != "UTC":
        return f"{local_str} ({tz_label}) • {utc_str}"
    return f"{local_str} • {utc_str}"


def format_email_notification(
    email_data: Dict[str, Any],
    notification_type: str = "immediate",
    privacy_mode: Optional[bool] = None,
) -> str:
    """
    Formats an email notification payload for delivery.
    Honors privacy mode to avoid sharing sensitive email text to group chats.
    """
    if privacy_mode is None:
        privacy_mode = settings.privacy_mode

    subject = email_data.get("subject", "(No Subject)")
    sender = email_data.get("sender", "Unknown Sender")
    category = email_data.get("category", "Other")
    gmail_id = email_data.get("gmail_message_id") or email_data.get("gmail_id") or ""
    link = build_gmail_link(gmail_id) if gmail_id else ""
    raw_deadline = email_data.get("extracted_deadline") or email_data.get("deadline")
    email_tz = email_data.get("email_timezone")
    tz_offset = email_data.get("timezone_offset")
    deadline_str = format_dual_time_string(raw_deadline, email_tz, tz_offset) if raw_deadline else ""

    if privacy_mode:
        msg_parts = [
            f"📧 *New Email Received* [{category}]",
            f"*From:* {sender}",
            f"*Subject:* {subject}",
        ]
        if link:
            msg_parts.append(f"🔗 [Open in Gmail]({link})")
        return "\n\n".join(msg_parts)

    msg_parts = [
        f"📧 *New Email* — *{category}*",
        f"*From:* {sender}",
        f"*Subject:* {subject}",
    ]

    # Include sanitized preview snippet
    body_snippet = (email_data.get("plain_body") or email_data.get("body") or "")[:200].strip()
    if body_snippet:
        msg_parts.append(f"*Preview:* {body_snippet}...")

    if deadline_str:
        msg_parts.append(f"⏰ *Extracted Deadline:* {deadline_str}")

    if link:
        msg_parts.append(f"🔗 [Open in Gmail]({link})")

    return "\n\n".join(msg_parts)


def format_digest_summary(emails: List[Dict[str, Any]]) -> str:
    """Combines multiple emails into a concise periodic digest notification."""
    if not emails:
        return "📭 *Gmail Summary Digest*\n\nNo new emails during this period."

    lines = [f"📬 *Gmail Summary Digest* ({len(emails)} new messages)\n"]
    for i, e in enumerate(emails, 1):
        subj = e.get("subject", "(No Subject)")
        sndr = e.get("sender", "Unknown")
        cat = e.get("category", "Other")
        lines.append(f"{i}. *[{cat}]* {subj} — _from {sndr}_")

    lines.append("\nLog in to your Gmail account or dashboard for full details.")
    return "\n".join(lines)


def send_to_channel(
    channel: str,
    target_id: str,
    message: str,
) -> Tuple[bool, Optional[str]]:
    """
    Directly sends message to specific channel.
    Returns (success, error_message).
    """
    try:
        if channel in ("whatsapp", "whatsapp_meta"):
            send_wa(target_id, message)
            return True, None
        elif channel == "telegram":
            send_tg(target_id, message)
            return True, None
        else:
            return False, f"Unsupported channel: {channel}"
    except Exception as exc:
        logger.error("Channel %s delivery failed for %s: %s", channel, target_id, exc)
        return False, str(exc)


def deliver_notification_idempotent(
    email_id: Optional[str],
    channel: str,
    destination_id: str,
    notification_type: str,
    message: str,
    idempotency_key: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Delivers notification with idempotency check against NotificationDelivery table.
    Ensures message is never sent twice with the same idempotency key.
    """
    db = get_db()
    if not idempotency_key:
        idempotency_key = f"{email_id or 'none'}_{channel}_{destination_id}_{notification_type}_{uuid.uuid4().hex[:6]}"

    # Check existing delivery
    existing = db.notification_deliveries.find_one({"idempotency_key": idempotency_key})
    if existing and existing.get("status") == DeliveryStatus.sent.value:
        logger.info("Skipping notification with key %s: already delivered", idempotency_key)
        return True, None

    success, error_msg = send_to_channel(channel, destination_id, message)

    status = DeliveryStatus.sent.value if success else DeliveryStatus.failed.value
    attempts = (existing.get("attempts", 0) + 1) if existing else 1
    sent_at = datetime.now(timezone.utc) if success else None

    delivery_doc = {
        "email_id": email_id,
        "user_id": user_id,
        "channel": channel,
        "destination_id": destination_id,
        "notification_type": notification_type,
        "idempotency_key": idempotency_key,
        "status": status,
        "attempts": attempts,
        "sent_at": sent_at,
        "last_error": error_msg,
        "created_at": datetime.now(timezone.utc),
    }

    if existing:
        db.notification_deliveries.update_one(
            {"idempotency_key": idempotency_key},
            {"$set": {
                "status": status,
                "attempts": attempts,
                "sent_at": sent_at,
                "last_error": error_msg,
            }}
        )
    else:
        db.notification_deliveries.insert_one(delivery_doc)

    return success, error_msg


def send_notification(destination: Any, message: str) -> Tuple[bool, Optional[str]]:
    """
    Sends message payload to resolved destination object or dict.
    Provides backwards compatibility for existing calls.
    """
    dtype = getattr(destination, "type", None) or (destination.get("type") if isinstance(destination, dict) else "")
    target_id = getattr(destination, "target_id", None) or (destination.get("target_id") if isinstance(destination, dict) else "")
    dest_id = getattr(destination, "id", None) or (destination.get("id") or destination.get("_id") if isinstance(destination, dict) else "")

    return deliver_notification_idempotent(
        email_id=None,
        channel=dtype,
        destination_id=target_id,
        notification_type="manual",
        message=message,
        idempotency_key=f"manual_{dest_id}_{uuid.uuid4().hex[:8]}",
    )
