"""
Pydantic model for SyncState records tracking incremental Gmail history IDs.
"""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class SyncState(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    account_identifier: str
    history_id: Optional[str] = None
    last_successful_sync: Optional[datetime] = None
    last_sync_status: str = "idle"

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }

