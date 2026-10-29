"""
Pydantic model for NotificationDelivery records with idempotency tracking.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DeliveryChannel(str, Enum):
    whatsapp = "whatsapp"
    telegram = "telegram"


class NotificationType(str, Enum):
    immediate = "immediate"
    summary = "summary"
    reminder = "reminder"
    test = "test"


class DeliveryStatus(str, Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class NotificationDelivery(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    email_id: Optional[str] = None
    channel: DeliveryChannel
    destination_id: str
    notification_type: NotificationType = NotificationType.immediate
    idempotency_key: str
    status: DeliveryStatus = DeliveryStatus.pending
    attempts: int = 0
    sent_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }

