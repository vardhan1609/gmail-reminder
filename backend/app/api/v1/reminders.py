"""
Reminders API endpoints (v1).
"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database.db import get_db
from app.middleware.auth import get_current_user
from app.models.db_models import UserModel
from app.models.reminder import ReminderStatus
from app.schemas.reminders import ReminderResponse, ReminderListResponse, ReminderResendResponse
from app.services.notifier import deliver_notification_idempotent
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/reminders", tags=["Reminders V1"])


@router.get("", response_model=ReminderListResponse)
def list_reminders(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_db),
):
    """List scheduled reminders with status filter and pagination."""
    # Tenant scope is mandatory; never return unowned/orphan legacy records.
    filter_dict = {"user_id": current_user.id}
    if status_filter:
        filter_dict["status"] = status_filter

    total = db.reminders.count_documents(filter_dict)
    reminders_cursor = db.reminders.find(filter_dict).sort("scheduled_at", -1).skip(skip).limit(limit)
    reminders_list = list(reminders_cursor)

    items = []
    for r in reminders_list:
        items.append(
            ReminderResponse(
                id=str(r.get("id") or r.get("_id")),
                email_id=r.get("email_id", ""),
                destination_id=r.get("destination_id", ""),
                message=r.get("message", ""),
                scheduled_at=r.get("scheduled_at") or r.get("reminder_time"),
                status=r.get("status", "pending"),
                retry_count=r.get("retry_count", r.get("retries", 0)),
                last_error=r.get("last_error"),
                sent_at=r.get("sent_at"),
                created_at=r.get("created_at"),
            )
        )

    return ReminderListResponse(reminders=items, total=total, limit=limit, skip=skip)


@router.post("/{id}/resend", response_model=ReminderResendResponse)
def resend_reminder(
    id: str,
    current_user: Optional[UserModel] = Depends(get_optional_current_user),
    db=Depends(get_db),
):
    """Retry or resend a reminder immediately."""
    reminder = db.reminders.find_one({"id": id, "user_id": current_user.id}) or db.reminders.find_one({"_id": id, "user_id": current_user.id})
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")


    dest_id = reminder.get("destination_id")
    dest = db.destinations.find_one({"id": dest_id, "user_id": current_user.id}) or db.destinations.find_one({"_id": dest_id, "user_id": current_user.id})
    if not dest:
        dest = db.destinations.find_one({"is_default": True, "user_id": current_user.id})

    if not dest:
        raise HTTPException(status_code=400, detail="No active destination associated with this reminder")

    channel = dest.get("type")
    target_id = dest.get("target_id")
    message = reminder.get("message", "")

    import uuid
    resend_key = f"resend_{id}_{uuid.uuid4().hex[:6]}"
    success, err = deliver_notification_idempotent(
        email_id=reminder.get("email_id"),
        channel=channel,
        destination_id=target_id,
        notification_type="reminder_resend",
        message=message,
        idempotency_key=resend_key,
        user_id=current_user.id,
    )

    if success:
        db.reminders.update_one(
            {"id": id, "user_id": current_user.id},
            {"$set": {
                "status": ReminderStatus.sent.value,
                "sent_at": datetime.now(timezone.utc),
                "last_error": None,
            }}
        )
        return ReminderResendResponse(id=id, status="sent", message="Reminder delivered successfully")
    else:
        db.reminders.update_one(
            {"id": id},
            {"$set": {
                "status": ReminderStatus.failed.value,
                "last_error": err,
            }}
        )
        raise HTTPException(status_code=502, detail=f"Delivery failed: {err}")

