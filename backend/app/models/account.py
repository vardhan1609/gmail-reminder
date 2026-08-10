from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class Account(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    email: str
    label: Optional[str] = None
    token_path: str
    active: bool = True
    calendar_sync_enabled: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
