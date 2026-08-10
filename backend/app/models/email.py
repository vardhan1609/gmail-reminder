from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class Email(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    account_id: str
    gmail_id: str
    sender: str
    subject: str
    body: Optional[str] = None
    category: str = "General"
    deadline: Optional[datetime] = None
    dedup_key: Optional[str] = None
    processed: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
