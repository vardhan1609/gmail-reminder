from datetime import datetime
from bson import ObjectId
from pymongo.database import Database

from app.utils.logger import get_logger

logger = get_logger(__name__)


def sync_email_deadline(db: Database, email_doc: dict):
    """
    Sync deadline to Google Calendar (if enabled on the account)
    and Outlook Calendar (if Outlook Client details are configured).
    """
    account = db.accounts.find_one({"_id": ObjectId(email_doc["account_id"])})
    if not account:
        logger.warning("Could not sync calendar: account %s not found", email_doc["account_id"])
        return

    # 1. Google Calendar sync (per account)
    if account.get("calendar_sync_enabled"):
        _sync_google(db, email_doc, account)

    # 2. Outlook Calendar sync (shared)
    from app.config import settings
    if settings.outlook_client_id and settings.outlook_client_secret:
        _sync_outlook(db, email_doc)


def _sync_google(db: Database, email_doc: dict, account: dict):
    email_id_str = str(email_doc["_id"])
    # Check if already synced
    existing = db.calendar_events.find_one({
        "email_id": email_id_str,
        "provider": "google"
    })
    if existing and existing.get("status") == "created":
        return

    event_id = str(ObjectId()) if not existing else str(existing["_id"])
    if not existing:
        db.calendar_events.insert_one({
            "_id": ObjectId(event_id),
            "email_id": email_id_str,
            "provider": "google",
            "status": "pending",
            "created_at": datetime.utcnow()
        })

    try:
        from app.services.google_calendar import create_event as google_create_event
        summary = f"Deadline: {email_doc['subject']}"
        description = f"Email from: {email_doc['sender']}\n\n{email_doc.get('body', '')[:1000]}"
        start = email_doc["deadline"]
        
        external_id = google_create_event(account["token_path"], summary, description, start)
        
        db.calendar_events.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {
                "status": "created",
                "external_event_id": external_id,
                "last_error": None
            }}
        )
        logger.info("Successfully synced deadline to Google calendar for email %s", email_id_str)
    except Exception as exc:
        logger.error("Failed to sync to Google calendar: %s", exc)
        db.calendar_events.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {
                "status": "failed",
                "last_error": str(exc)
            }}
        )


def _sync_outlook(db: Database, email_doc: dict):
    email_id_str = str(email_doc["_id"])
    # Check if already synced
    existing = db.calendar_events.find_one({
        "email_id": email_id_str,
        "provider": "outlook"
    })
    if existing and existing.get("status") == "created":
        return

    event_id = str(ObjectId()) if not existing else str(existing["_id"])
    if not existing:
        db.calendar_events.insert_one({
            "_id": ObjectId(event_id),
            "email_id": email_id_str,
            "provider": "outlook",
            "status": "pending",
            "created_at": datetime.utcnow()
        })

    try:
        from app.services.outlook_calendar import create_event as outlook_create_event
        summary = f"Deadline: {email_doc['subject']}"
        description = f"Email from: {email_doc['sender']}\n\n{email_doc.get('body', '')[:1000]}"
        start = email_doc["deadline"]
        
        external_id = outlook_create_event(summary, description, start)
        
        db.calendar_events.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {
                "status": "created",
                "external_event_id": external_id,
                "last_error": None
            }}
        )
        logger.info("Successfully synced deadline to Outlook calendar for email %s", email_id_str)
    except Exception as exc:
        logger.error("Failed to sync to Outlook calendar: %s", exc)
        db.calendar_events.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {
                "status": "failed",
                "last_error": str(exc)
            }}
        )
