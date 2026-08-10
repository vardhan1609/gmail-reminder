import enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class ReminderStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class Reminder(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    email_id: str
    destination_id: str
    message: str
    reminder_time: datetime
    status: ReminderStatus = ReminderStatus.pending
    retries: int = 0
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
