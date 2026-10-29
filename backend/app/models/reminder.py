"""
Pydantic Reminder model.
"""
from datetime import datetime, timezone
import enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class ReminderStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class Reminder(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    email_id: str
    destination_id: str
    message: str
    scheduled_at: datetime
    reminder_time: Optional[datetime] = None  # backward compatibility
    status: ReminderStatus = ReminderStatus.pending
    retry_count: int = 0
    retries: Optional[int] = None  # backward compatibility
    last_error: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: Any) -> None:
        if not self.reminder_time and self.scheduled_at:
            self.reminder_time = self.scheduled_at
        if not self.scheduled_at and self.reminder_time:
            self.scheduled_at = self.reminder_time
        if self.retries is None:
            self.retries = self.retry_count

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
