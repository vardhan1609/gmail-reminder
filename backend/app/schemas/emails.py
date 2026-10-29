from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class EmailResponse(BaseModel):
    id: str
    account_id: Optional[str] = None
    gmail_message_id: str
    gmail_thread_id: Optional[str] = None
    sender: str
    recipients: Optional[str] = None
    subject: str
    received_at: Optional[datetime] = None
    category: str
    extracted_deadline: Optional[datetime] = None
    confidence_score: float
    ambiguous_date: bool
    plain_body: Optional[str] = None
    labels: Optional[str] = None
    processing_status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EmailListResponse(BaseModel):
    emails: List[EmailResponse]
    total: int
    limit: int
    skip: int

