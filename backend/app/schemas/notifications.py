from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class NotificationTestRequest(BaseModel):
    channel: str = Field(..., description="whatsapp or telegram")
    destination_id: Optional[str] = Field(None, description="Target JID, phone, or chat_id")
    message: Optional[str] = Field("🔔 Test notification from Gmail Reminder System", description="Message text")


class NotificationDeliveryResponse(BaseModel):
    id: str
    email_id: Optional[str] = None
    channel: str
    destination_id: str
    notification_type: str
    idempotency_key: str
    status: str
    attempts: int
    sent_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: Optional[datetime] = None


class NotificationDeliveryListResponse(BaseModel):
    deliveries: List[NotificationDeliveryResponse]
    total: int
    limit: int
    skip: int

