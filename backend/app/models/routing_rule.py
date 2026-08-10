from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class RoutingRule(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    account_id: Optional[str] = None
    category: Optional[str] = None
    destination_id: str
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
