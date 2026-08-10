import enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class CalendarProvider(str, enum.Enum):
    google = "google"
    outlook = "outlook"


class CalendarEvent(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    email_id: str
    provider: CalendarProvider
    external_event_id: Optional[str] = None
    status: str = "pending"
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
