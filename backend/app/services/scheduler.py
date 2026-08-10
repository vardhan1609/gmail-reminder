from datetime import datetime, timedelta
import threading
import time
from bson import ObjectId
from pymongo.database import Database

from app.config import settings
from app.database.db import get_db
from app.models.reminder import ReminderStatus
from app.services.calendar_sync import sync_email_deadline
from app.services.classifier import classify_email
from app.services.deadline_extractor import extract_deadline
from app.services.gmail_service import list_new_message_ids, get_message
from app.services.notifier import send_notification
from app.services.routing import resolve_destinations
from app.utils.logger import get_logger

logger = get_logger(__name__)

_scheduler_thread: threading.Thread | None = None
_shutdown_event = threading.Event()


def start_scheduler():
    global _scheduler_thread, _shutdown_event
    if _scheduler_thread is not None:
        return
    _shutdown_event.clear()
    _scheduler_thread = threading.Thread(target=_run_scheduler, daemon=True)
    _scheduler_thread.start()
    logger.info(
        "Scheduler started: polling all accounts every %ds, dispatching reminders every 60s",
        settings.poll_interval_seconds,
    )


def stop_scheduler():
    global _scheduler_thread, _shutdown_event
    if _scheduler_thread is None:
        return
    _shutdown_event.set()
    _scheduler_thread.join()
    _scheduler_thread = None
    logger.info("Scheduler stopped")


def _run_scheduler():
    db = get_db()
    last_poll_time = datetime.min

    while not _shutdown_event.is_set():
        now = datetime.utcnow()

        # 1. Poll accounts
        if (now - last_poll_time).total_seconds() >= settings.poll_interval_seconds:
            try:
                _poll_all_accounts(db)
                last_poll_time = now
            except Exception as exc:
                logger.error("Poll cycle failed: %s", exc)

        # 2. Dispatch reminders
        try:
            dispatch_due_reminders(db)
        except Exception as exc:
            logger.error("Dispatch cycle failed: %s", exc)

        # Sleep in small steps to shutdown quickly
        for _ in range(30):
            if _shutdown_event.is_set():
                break
            time.sleep(2)


def _poll_all_accounts(db: Database):
    accounts = list(db.accounts.find({"active": True}))
    if not accounts:
        logger.warning("No active Gmail accounts connected; visit /accounts/gmail/login.")
        return

    for account in accounts:
        account_id_str = str(account["_id"])
        logger.info("Polling account: %s", account["email"])
        try:
            token_path = account["token_path"]
            message_ids = list_new_message_ids(token_path)
            for msg_id in message_ids:
                msg = get_message(token_path, msg_id)
                body = msg.get("plain_text") or msg.get("snippet") or ""
                raw_email = {
                    "gmail_id": msg["gmail_id"],
                    "sender": msg["sender"],
                    "subject": msg["subject"],
                    "body": body,
                }
                _process_email(db, account_id_str, raw_email)
        except Exception as exc:
            logger.error("Failed to poll account %s: %s", account["email"], exc)


def _process_email(db: Database, account_id: str, raw_email: dict):
    # Unique constraint check
    gmail_id = raw_email["gmail_id"]
    if db.emails.find_one({"account_id": account_id, "gmail_id": gmail_id}):
        return  # already processed

    # Classification & extraction
    subject = raw_email["subject"]
    body = raw_email.get("body", "")
    sender = raw_email["sender"]

    # Calculate dedup key
    normalized_subject = subject.lower().replace("re:", "").replace("fwd:", "").strip()
    dedup_key = f"{sender.lower()}|{normalized_subject}"

    # Check for recent duplicate within 24h
    time_limit = datetime.utcnow() - timedelta(hours=24)
    duplicate = db.emails.find_one({
        "account_id": account_id,
        "dedup_key": dedup_key,
        "created_at": {"$gte": time_limit}
    })
    if duplicate:
        logger.info("Skipping email %r: duplicate of %s", subject, duplicate["_id"])
        return

    # Extract deadline and classify
    category = classify_email(subject, body)
    deadline = extract_deadline(subject, body)

    # Insert email
    email_doc = {
        "account_id": account_id,
        "gmail_id": gmail_id,
        "sender": sender,
        "subject": subject,
        "body": body,
        "category": category,
        "deadline": deadline,
        "dedup_key": dedup_key,
        "processed": False,
        "created_at": datetime.utcnow()
    }
    db.emails.insert_one(email_doc)
    email_id_str = str(email_doc["_id"])

    logger.info(
        "Email parsed: %r [Category: %s, Deadline: %s]",
        subject, category, deadline
    )

    if not deadline:
        db.emails.update_one({"_id": ObjectId(email_id_str)}, {"$set": {"processed": True}})
        return

    # Routing & reminders creation
    destinations = resolve_destinations(db, account_id, category)
    if not destinations:
        logger.warning("No destinations resolved for email %s", email_id_str)
        db.emails.update_one({"_id": ObjectId(email_id_str)}, {"$set": {"processed": True}})
        return

    # Create reminders based on offsets
    offsets = settings.reminder_offsets_minutes
    reminders_created = 0
    for dest in destinations:
        dest_id_str = str(dest["_id"])
        for offset in offsets:
            reminder_time = deadline - timedelta(minutes=offset)
            if reminder_time <= datetime.utcnow():
                continue  # past due

            # Create message template
            message = (
                f"🚨 *{category} Deadline Reminder*\n\n"
                f"*Subject:* {subject}\n"
                f"*From:* {sender}\n"
                f"*Deadline:* {deadline.strftime('%Y-%m-%d %I:%M %p')} UTC\n"
                f"🕒 *Due in:* {offset // 60} hours"
            )

            reminder_doc = {
                "email_id": email_id_str,
                "destination_id": dest_id_str,
                "message": message,
                "reminder_time": reminder_time,
                "status": ReminderStatus.pending.value,
                "retries": 0,
                "created_at": datetime.utcnow()
            }
            db.reminders.insert_one(reminder_doc)
            reminders_created += 1

    # Calendar synchronization
    sync_email_deadline(db, email_doc)

    db.emails.update_one(
        {"_id": ObjectId(email_id_str)},
        {"$set": {"processed": True}}
    )
    logger.info("Created %d reminders for email %s", reminders_created, email_id_str)


def dispatch_due_reminders(db: Database) -> int:
    now = datetime.utcnow()
    due_reminders = list(db.reminders.find({
        "status": ReminderStatus.pending.value,
        "reminder_time": {"$lte": now}
    }))

    if not due_reminders:
        return 0

    sent_count = 0
    for r in due_reminders:
        r_id_str = str(r["_id"])
        dest = db.destinations.find_one({"_id": ObjectId(r["destination_id"])})
        if not dest:
            db.reminders.update_one(
                {"_id": ObjectId(r_id_str)},
                {"$set": {"status": ReminderStatus.failed.value, "last_error": "Destination missing"}}
            )
            continue

        # Build a namespace object for notifier
        class _Dest:
            pass
        dest_obj = _Dest()
        dest_obj.type = dest.get("type")
        dest_obj.target_id = dest.get("target_id")

        success, error_msg = send_notification(dest_obj, r["message"])
        if success:
            db.reminders.update_one(
                {"_id": ObjectId(r_id_str)},
                {"$set": {
                    "status": ReminderStatus.sent.value,
                    "sent_at": datetime.utcnow()
                }}
            )
            sent_count += 1
        else:
            retries = r.get("retries", 0) + 1
            status = ReminderStatus.failed.value if retries >= 3 else ReminderStatus.pending.value
            db.reminders.update_one(
                {"_id": ObjectId(r_id_str)},
                {"$set": {
                    "status": status,
                    "retries": retries,
                    "last_error": error_msg
                }}
            )

    return sent_count
