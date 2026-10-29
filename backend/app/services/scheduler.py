"""
Background worker and scheduler:
- Continuous polling of connected Gmail accounts
- Incremental history sync with fallback
- Normalization, HTML sanitization, and deduplication
- Category classification and deadline extraction with confidence scoring
- Immediate notifications vs summary digest notifications
- Reminder creation with configurable offsets
- Due reminder dispatch with exponential backoff and retry handling
- Channel independence and worker restart recovery
"""
from datetime import datetime, timezone, timedelta
import threading
import time
from typing import Dict, List, Optional, Any
from bson import ObjectId

from app.config import settings
from app.database.db import get_db
from app.models.reminder import ReminderStatus
from app.models.notification_delivery import DeliveryStatus
from app.services.calendar_sync import sync_email_deadline
from app.services.classifier import classify_email
from app.services.deadline_extractor import get_deadline_extraction
from app.services.gmail_service import (
    sync_messages_incremental,
    get_message,
    list_messages_paginated,
)
from app.services.notifier import (
    deliver_notification_idempotent,
    format_email_notification,
    format_digest_summary,
)
from app.services.parser import parse_email
from app.services.routing import resolve_destinations
from app.utils.logger import get_logger
from app.websocket import publish_event, EventType

logger = get_logger(__name__)

_scheduler_thread: threading.Thread | None = None
_shutdown_event = threading.Event()
_digest_buffer: List[Dict[str, Any]] = []
_last_digest_time = datetime.now(timezone.utc)


def start_scheduler():
    global _scheduler_thread, _shutdown_event
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _shutdown_event.clear()
    _scheduler_thread = threading.Thread(target=_run_scheduler, daemon=True, name="SchedulerWorker")
    _scheduler_thread.start()
    logger.info(
        "Scheduler worker started: poll interval %ds, notification mode '%s'",
        settings.poll_interval_seconds,
        settings.notification_mode,
    )


def stop_scheduler():
    global _scheduler_thread, _shutdown_event
    if _scheduler_thread is None:
        return
    _shutdown_event.set()
    _scheduler_thread.join(timeout=10.0)
    _scheduler_thread = None
    logger.info("Scheduler worker stopped cleanly")


def _run_scheduler():
    db = get_db()
    last_poll_time = datetime.min.replace(tzinfo=timezone.utc)

    while not _shutdown_event.is_set():
        now = datetime.now(timezone.utc)

        # 1. Email synchronization cycle
        if (now - last_poll_time).total_seconds() >= settings.poll_interval_seconds:
            try:
                _poll_all_accounts(db)
                last_poll_time = now
            except Exception as exc:
                logger.error("Poll cycle encountered an error: %s", exc)

        # 2. Summary digest dispatch if applicable
        if settings.notification_mode == "summary":
            _check_and_dispatch_digest(db)

        # 3. Dispatch scheduled reminders
        try:
            dispatch_due_reminders(db)
        except Exception as exc:
            logger.error("Reminder dispatch cycle failed: %s", exc)

        # Quick interruptible sleep
        for _ in range(15):
            if _shutdown_event.is_set():
                break
            time.sleep(2)


def _poll_all_accounts(db):
    accounts = list(db.accounts.find({"active": True}))
    if hasattr(db, "gmail_connections"):
        accounts += list(db.gmail_connections.find({"active": True}))
    if not accounts:
        logger.info("No active Gmail accounts to poll.")
        return

    for account in accounts:
        acc_id = str(account.get("id") or account.get("_id"))
        email_addr = account.get("email", "")
        token_path = account.get("token_path", "")
        user_id = account.get("user_id")

        if not token_path or not os.path.isfile(token_path):
            logger.warning("Account %s skipped: token file missing or invalid (%s)", email_addr, token_path)
            continue

        logger.info("Synchronizing account: %s", email_addr)
        if user_id:
            publish_event(
                user_id,
                EventType.GMAIL_SYNC_STARTED,
                {"account_id": acc_id, "email": email_addr, "started_at": datetime.now(timezone.utc).isoformat()},
            )

        try:
            # Check or load SyncState
            sync_state = db.sync_states.find_one({"account_identifier": email_addr})
            last_history_id = sync_state.get("history_id") if sync_state else None

            # Fetch new messages
            msg_ids, new_history_id = sync_messages_incremental(token_path, last_history_id)
            logger.info("Found %d new message IDs for %s", len(msg_ids), email_addr)

            for msg_id in msg_ids:
                if _shutdown_event.is_set():
                    break
                raw_msg = get_message(token_path, msg_id)
                if raw_msg:
                    _process_email(db, acc_id, raw_msg, user_id=user_id)

            # Update SyncState
            now = datetime.now(timezone.utc)
            if sync_state:
                db.sync_states.update_one(
                    {"account_identifier": email_addr},
                    {"$set": {
                        "history_id": new_history_id,
                        "last_successful_sync": now,
                        "last_sync_status": "success",
                    }}
                )
            else:
                db.sync_states.insert_one({
                    "account_identifier": email_addr,
                    "history_id": new_history_id,
                    "last_successful_sync": now,
                    "last_sync_status": "success",
                })

            if hasattr(db, "gmail_connections"):
                db.gmail_connections.update_one(
                    {"email": email_addr},
                    {"$set": {
                        "last_sync_at": now,
                        "last_sync_status": "idle",
                        "history_id": new_history_id,
                    }}
                )

            if user_id:
                publish_event(
                    user_id,
                    EventType.GMAIL_SYNC_COMPLETED,
                    {
                        "account_id": acc_id,
                        "email": email_addr,
                        "new_messages_count": len(msg_ids),
                        "completed_at": now.isoformat(),
                    },
                )

        except Exception as exc:
            logger.error("Failed to sync account %s: %s", email_addr, exc)
            db.sync_states.update_one(
                {"account_identifier": email_addr},
                {"$set": {"last_sync_status": f"failed: {str(exc)[:100]}"}},
                upsert=True,
            )
            if hasattr(db, "gmail_connections"):
                db.gmail_connections.update_one(
                    {"email": email_addr},
                    {"$set": {"last_sync_status": f"failed: {str(exc)[:100]}"}},
                )
            if user_id:
                publish_event(
                    user_id,
                    EventType.GMAIL_SYNC_FAILED,
                    {
                        "account_id": acc_id,
                        "email": email_addr,
                        "error": str(exc)[:100],
                        "failed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )


def _process_email(db, account_id: str, raw_email: Dict[str, Any], user_id: Optional[str] = None):
    gmail_id = raw_email.get("gmail_message_id") or raw_email.get("gmail_id")
    if not gmail_id:
        return

    # 1. Dedup check: Unique gmail_message_id
    existing = db.emails.find_one({"gmail_message_id": gmail_id})
    if existing:
        return

    # 2. Parse and sanitize email body
    parsed = parse_email(raw_email)
    body_text = parsed.get("body_text", "")
    html_body = parsed.get("html", "")
    subject = parsed.get("subject", "(no subject)")
    sender = parsed.get("sender", "unknown")
    recipients = parsed.get("recipients", "")
    received_at = parsed.get("received_at") or datetime.now(timezone.utc)
    thread_id = parsed.get("gmail_thread_id")
    labels = parsed.get("labels", [])
    attachments = parsed.get("attachments", [])

    # 3. Soft deduplication check (24h window for duplicate subject + sender)
    norm_subject = subject.lower().replace("re:", "").replace("fwd:", "").strip()
    dedup_key = f"{sender.lower()}|{norm_subject}"
    time_limit = datetime.now(timezone.utc) - timedelta(hours=24)
    dup = db.emails.find_one({
        "account_id": account_id,
        "sender": sender,
        "subject": subject,
        "created_at": {"$gte": time_limit},
    })
    if dup:
        logger.info("Skipping duplicate email '%s' within 24h", subject)
        return

    # 4. Classification (never discards email, defaults to Other)
    category = classify_email(subject, body_text)

    # 5. Deadline and date extraction (relative to email's received time and location timezone)
    ref_time = raw_email.get("orig_received_at") or raw_email.get("received_at") or received_at
    extraction = get_deadline_extraction(subject, body_text, reference_time=ref_time)
    deadline = extraction.deadline
    confidence = extraction.confidence_score
    ambiguous = extraction.is_ambiguous

    # 6. Store email record
    import json
    email_doc = {
        "account_id": account_id,
        "user_id": user_id,
        "gmail_message_id": gmail_id,
        "gmail_thread_id": thread_id,
        "sender": sender,
        "recipients": recipients if isinstance(recipients, str) else ", ".join(recipients),
        "subject": subject,
        "received_at": received_at,
        "category": category,
        "extracted_deadline": deadline,
        "confidence_score": confidence,
        "ambiguous_date": ambiguous,
        "plain_body": body_text,
        "html_body": html_body,
        "attachments_meta": json.dumps(attachments),
        "labels": ", ".join(labels) if isinstance(labels, list) else str(labels),
        "processing_status": "completed",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    inserted = db.emails.insert_one(email_doc)
    email_id = str(inserted.get("id") or inserted.get("_id"))
    logger.info("Processed email '%s' [%s] -> ID: %s", subject, category, email_id)

    if user_id:
        received_iso = received_at.isoformat() if hasattr(received_at, "isoformat") else str(received_at)
        publish_event(
            user_id,
            EventType.EMAIL_RECEIVED,
            {
                "email_id": email_id,
                "subject": subject,
                "sender": sender,
                "category": category,
                "received_at": received_iso,
                "has_deadline": bool(deadline),
            },
        )
        publish_event(
            user_id,
            EventType.EMAIL_CLASSIFIED,
            {
                "email_id": email_id,
                "category": category,
                "confidence_score": confidence,
                "extracted_deadline": deadline.isoformat() if deadline else None,
            },
        )

    # 7. Check if historical cutoff prevents notification storm
    is_historical = False
    if settings.notification_cutoff_hours > 0 and received_at:
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=settings.notification_cutoff_hours)
        if received_at < cutoff_dt:
            is_historical = True
            logger.info("Email '%s' is older than %d hours; skipping immediate notification.", subject, settings.notification_cutoff_hours)

    # 8. Dispatch notification according to mode
    destinations = resolve_destinations(db, account_id, category)

    if not is_historical and destinations:
        if settings.notification_mode == "immediate":
            for dest in destinations:
                dest_type = dest.get("type")
                target_id = dest.get("target_id")
                msg_text = format_email_notification(email_doc)
                idempotency_key = f"imm_{email_id}_{dest_type}_{target_id}"
                deliver_notification_idempotent(
                    email_id=email_id,
                    channel=dest_type,
                    destination_id=target_id,
                    notification_type="immediate",
                    message=msg_text,
                    idempotency_key=idempotency_key,
                    user_id=user_id,
                )
        elif settings.notification_mode == "summary":
            _digest_buffer.append(email_doc)

    # 9. Schedule deadline reminders if a confident submission deadline exists
    if deadline and deadline > datetime.now(timezone.utc) and not ambiguous:
        offsets = settings.reminder_offsets_minutes
        for dest in destinations:
            dest_id = str(dest.get("id") or dest.get("_id"))
            for offset in offsets:
                scheduled_time = deadline - timedelta(minutes=offset)
                if scheduled_time <= datetime.now(timezone.utc):
                    continue  # already in the past

                # Format dual timezone (email/location timezone and UTC)
                tz_offset = raw_email.get("timezone_offset") or ""
                tz_name = raw_email.get("email_timezone") or "Local"
                local_deadline = deadline
                if tz_offset:
                    try:
                        hours = int(tz_offset[:3])
                        mins = int(tz_offset[0] + tz_offset[3:])
                        email_tz = timezone(timedelta(hours=hours, minutes=mins))
                        local_deadline = deadline.astimezone(email_tz)
                    except Exception:
                        pass
                local_str = local_deadline.strftime("%Y-%m-%d %I:%M %p")
                utc_str = deadline.strftime("%Y-%m-%d %I:%M %p UTC")
                deadline_display = f"{local_str} ({tz_name}) • {utc_str}" if tz_name != "UTC" else utc_str

                reminder_message = (
                    f"⏰ *{category} Deadline Reminder*\n\n"
                    f"*Subject:* {subject}\n"
                    f"*From:* {sender}\n"
                    f"*Deadline:* {deadline_display}\n"
                    f"⏳ *Due in:* {offset // 60} hours\n\n"
                    f"🔗 [Open Email](https://mail.google.com/mail/u/0/#inbox/{gmail_id})"
                )

                rem_doc = {
                    "email_id": email_id,
                    "user_id": user_id,
                    "destination_id": dest_id,
                    "message": reminder_message,
                    "scheduled_at": scheduled_time,
                    "status": ReminderStatus.pending.value,
                    "retry_count": 0,
                    "created_at": datetime.now(timezone.utc),
                }
                inserted_rem = db.reminders.insert_one(rem_doc)
                rem_id = str(inserted_rem.get("id") or inserted_rem.get("_id") or "")
                logger.info("Scheduled reminder for '%s' at %s", subject, scheduled_time)

                if user_id:
                    publish_event(
                        user_id,
                        EventType.REMINDER_CREATED,
                        {
                            "reminder_id": rem_id,
                            "email_id": email_id,
                            "scheduled_at": scheduled_time.isoformat(),
                            "message_preview": subject,
                            "status": "pending",
                        },
                    )

        # Calendar synchronization
        try:
            sync_email_deadline(db, email_doc)
        except Exception as exc:
            logger.warning("Calendar sync error for %s: %s", email_id, exc)


def _check_and_dispatch_digest(db):
    """Flushes buffered emails in summary mode at periodic intervals."""
    global _digest_buffer, _last_digest_time
    now = datetime.now(timezone.utc)
    interval_sec = settings.digest_interval_minutes * 60

    if (now - _last_digest_time).total_seconds() >= interval_sec and _digest_buffer:
        digest_emails = list(_digest_buffer)
        _digest_buffer.clear()
        _last_digest_time = now

        text = format_digest_summary(digest_emails)
        # Deliver digest to default destinations
        default_dests = list(db.destinations.find({"is_default": True, "active": True}))
        if not default_dests:
            default_dests = list(db.destinations.find({"active": True}))

        for dest in default_dests:
            dest_type = dest.get("type")
            target_id = dest.get("target_id")
            key = f"digest_{now.strftime('%Y%m%d%H%M')}_{dest_type}_{target_id}"
            deliver_notification_idempotent(
                email_id=None,
                channel=dest_type,
                destination_id=target_id,
                notification_type="summary",
                message=text,
                idempotency_key=key,
            )


def dispatch_due_reminders(db) -> int:
    """
    Finds and dispatches due reminders with exponential backoff on retry.
    Dispatches independently per channel (failure in one does not block others).
    """
    now = datetime.now(timezone.utc)
    due_reminders = list(db.reminders.find({
        "status": ReminderStatus.pending.value,
        "scheduled_at": {"$lte": now},
    }))

    if not due_reminders:
        return 0

    sent_count = 0
    for r in due_reminders:
        r_id = str(r.get("id") or r.get("_id"))
        dest_id = r.get("destination_id")
        dest = db.destinations.find_one({"id": dest_id}) or db.destinations.find_one({"_id": dest_id})
        if not dest:
            # Fallback to default
            dest = db.destinations.find_one({"is_default": True})

        if not dest:
            db.reminders.update_one(
                {"id": r_id},
                {"$set": {
                    "status": ReminderStatus.failed.value,
                    "last_error": f"Destination {dest_id} not found",
                }}
            )
            continue

        channel = dest.get("type")
        target_id = dest.get("target_id")
        message = r.get("message", "")
        idempotency_key = f"reminder_{r_id}_{channel}_{r.get('retry_count', 0)}"

        user_id = r.get("user_id")
        deliver_kwargs = {
            "email_id": r.get("email_id"),
            "channel": channel,
            "destination_id": target_id,
            "notification_type": "reminder",
            "message": message,
            "idempotency_key": idempotency_key,
        }
        try:
            import inspect
            sig = inspect.signature(deliver_notification_idempotent)
            if "user_id" in sig.parameters:
                deliver_kwargs["user_id"] = user_id
        except Exception:
            pass
        success, err = deliver_notification_idempotent(**deliver_kwargs)

        if success:
            db.reminders.update_one(
                {"id": r_id},
                {"$set": {
                    "status": ReminderStatus.sent.value,
                    "sent_at": datetime.now(timezone.utc),
                    "last_error": None,
                }}
            )
            sent_count += 1
            if user_id:
                publish_event(
                    user_id,
                    EventType.REMINDER_UPDATED,
                    {
                        "reminder_id": r_id,
                        "email_id": r.get("email_id"),
                        "status": ReminderStatus.sent.value,
                        "retry_count": r.get("retry_count", 0),
                    },
                )
        else:
            retry_count = r.get("retry_count", 0) + 1
            # Exponential backoff delay: 1 min, 2 min, 4 min, etc.
            backoff_minutes = 2 ** retry_count
            new_scheduled_at = now + timedelta(minutes=backoff_minutes)
            new_status = ReminderStatus.failed.value if retry_count >= 3 else ReminderStatus.pending.value

            db.reminders.update_one(
                {"id": r_id},
                {"$set": {
                    "status": new_status,
                    "retry_count": retry_count,
                    "scheduled_at": new_scheduled_at if new_status == ReminderStatus.pending.value else r.get("scheduled_at"),
                    "last_error": err,
                }}
            )
            if user_id:
                publish_event(
                    user_id,
                    EventType.REMINDER_UPDATED,
                    {
                        "reminder_id": r_id,
                        "email_id": r.get("email_id"),
                        "status": new_status,
                        "retry_count": retry_count,
                        "last_error": err,
                    },
                )

    return sent_count
