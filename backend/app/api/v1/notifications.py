"""
Notifications API endpoints (v1).
"""
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database.db import get_db
from app.middleware.auth import get_current_user
from app.models.db_models import UserModel
from app.schemas.notifications import (
    NotificationTestRequest,
    NotificationDeliveryResponse,
    NotificationDeliveryListResponse,
)
from app.services.notifier import deliver_notification_idempotent
from app.services.telegram import validate_chat_id

router = APIRouter(prefix="/notifications", tags=["Notifications V1"])


@router.post("/test")
def send_test_notification(
    payload: NotificationTestRequest,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_db),
):
    """Sends a manual test notification to verified destination."""
    channel = payload.channel.lower()
    if channel not in ("whatsapp", "whatsapp_meta", "telegram"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported channel: {channel}. Must be 'whatsapp' or 'telegram'.",
        )

    target_id = payload.destination_id
    if not target_id:
        # Check for registered destination
        dest = db.destinations.find_one({"user_id": current_user.id, "type": channel, "is_default": True}) or db.destinations.find_one({"user_id": current_user.id, "type": channel})
        if dest:
            target_id = dest.get("target_id")

    if target_id:
        owned = db.destinations.find_one({"user_id": current_user.id, "type": channel, "target_id": target_id})
        if not owned:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification destination not found.")

    if not target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No destination_id provided and no default {channel} destination configured.",
        )

    if channel == "telegram" and not validate_chat_id(target_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Telegram chat_id format: {target_id}",
        )

    test_key = f"test_{channel}_{target_id}_{uuid.uuid4().hex[:6]}"
    success, err = deliver_notification_idempotent(
        email_id=None,
        channel=channel,
        destination_id=target_id,
        notification_type="test",
        message=payload.message or "🔔 Test notification from Gmail Reminder System",
        idempotency_key=test_key,
        user_id=current_user.id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Test notification delivery failed. Please try again later.",
        )

    return {"status": "sent", "channel": channel, "destination_id": target_id}


@router.get("", response_model=NotificationDeliveryListResponse)
def list_notifications(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    channel: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_db),
):
    """View delivery audit trail and history."""
    # Never expose another tenant's data or records without a tenant owner.
    filter_dict = {"user_id": current_user.id}
    if channel:
        filter_dict["channel"] = channel
    if status_filter:
        filter_dict["status"] = status_filter

    total = db.notification_deliveries.count_documents(filter_dict)
    cursor = db.notification_deliveries.find(filter_dict).sort("created_at", -1).skip(skip).limit(limit)
    items = []
    for d in cursor:
        items.append(
            NotificationDeliveryResponse(
                id=str(d.get("id") or d.get("_id")),
                email_id=d.get("email_id"),
                channel=d.get("channel", "unknown"),
                destination_id=d.get("destination_id", ""),
                notification_type=d.get("notification_type", "immediate"),
                idempotency_key=d.get("idempotency_key", ""),
                status=d.get("status", "pending"),
                attempts=d.get("attempts", 1),
                sent_at=d.get("sent_at"),
                last_error=d.get("last_error"),
                created_at=d.get("created_at"),
            )
        )

    return NotificationDeliveryListResponse(deliveries=items, total=total, limit=limit, skip=skip)

