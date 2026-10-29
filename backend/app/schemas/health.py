from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class DestinationHealth(BaseModel):
    id: str
    name: str
    type: str
    ready: bool


class HealthResponse(BaseModel):
    status: str
    time: datetime
    version: str = "2.0.0"
    destinations: List[DestinationHealth]
    pending_reminders: int


class ReadinessChecks(BaseModel):
    database: bool
    tokens_storage: bool
    telegram: bool
    whatsapp: bool


class ReadyResponse(BaseModel):
    ready: bool
    checks: ReadinessChecks
    timestamp: datetime

