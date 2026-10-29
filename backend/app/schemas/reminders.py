from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ReminderResponse(BaseModel):
    id: str
    email_id: str
    destination_id: str
    message: str
    scheduled_at: datetime
    status: str
    retry_count: int
    last_error: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ReminderListResponse(BaseModel):
    reminders: List[ReminderResponse]
    total: int
    limit: int
    skip: int


class ReminderResendResponse(BaseModel):
    id: str
    status: str
    message: str

