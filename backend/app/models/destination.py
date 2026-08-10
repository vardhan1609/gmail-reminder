import enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class DestinationType(str, enum.Enum):
    whatsapp = "whatsapp"
    telegram = "telegram"


class Destination(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    type: DestinationType
    name: str
    target_id: str
    is_default: bool = False
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
