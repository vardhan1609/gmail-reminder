from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database

from app.database.db import get_db
from app.models.reminder import ReminderStatus
from app.services import notifier
from app.services.scheduler import dispatch_due_reminders
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Logs & Status"])


@router.get("/emails")
def list_emails(
    limit: int = Query(50, ge=1, le=200),
    db: Database = Depends(get_db)
):
    """List parsed and classified emails."""
    emails = list(db.emails.find().sort("created_at", -1).limit(limit))
    for e in emails:
        e["id"] = str(e.pop("_id"))
    return emails


@router.get("/reminders")
def list_reminders(
    limit: int = Query(50, ge=1, le=200),
    db: Database = Depends(get_db)
):
    """List generated and dispatched reminders."""
    reminders = list(db.reminders.find().sort("reminder_time", -1).limit(limit))
    for r in reminders:
        r["id"] = str(r.pop("_id"))
    return reminders


@router.post("/reminders/send-due-now")
def send_due_now(db: Database = Depends(get_db)):
    """Manually flush any due reminders immediately."""
    count = dispatch_due_reminders(db)
    return {"reminders_sent": count}


@router.get("/health")
def health(db: Database = Depends(get_db)):
    try:
        destinations = list(db.destinations.find({"active": True}))

        # Build a lightweight destination-like object for notifier
        dest_status = []
        for d in destinations:
            class _Dest:
                pass
            dest_obj = _Dest()
            dest_obj.type = d.get("type")
            dest_obj.target_id = d.get("target_id")
            dest_status.append({
                "id": str(d["_id"]),
                "name": d.get("name"),
                "type": d.get("type"),
                "ready": notifier.destination_is_ready(dest_obj),
            })

        pending_count = db.reminders.count_documents({"status": ReminderStatus.pending.value})
        return {
            "status": "ok",
            "time": datetime.now(timezone.utc),
            "destinations": dest_status,
            "pending_reminders": pending_count,
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "time": datetime.now(timezone.utc),
            "error": f"MongoDB: {exc}",
            "destinations": [],
            "pending_reminders": 0,
        }
