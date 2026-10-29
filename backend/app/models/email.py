"""
Pydantic Email model representing processed messages.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Email(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    account_id: Optional[str] = None
    gmail_message_id: str
    gmail_id: Optional[str] = None  # backward compatibility
    gmail_thread_id: Optional[str] = None
    sender: str
    recipients: Optional[str] = None
    subject: str
    received_at: Optional[datetime] = None
    category: str = "Other"
    extracted_deadline: Optional[datetime] = None
    deadline: Optional[datetime] = None  # backward compatibility
    confidence_score: float = 0.0
    ambiguous_date: bool = False
    plain_body: Optional[str] = None
    body: Optional[str] = None  # backward compatibility
    html_body: Optional[str] = None
    attachments_meta: Optional[str] = None
    labels: Optional[str] = None
    processing_status: str = "pending"
    processed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: Any) -> None:
        if not self.gmail_id and self.gmail_message_id:
            self.gmail_id = self.gmail_message_id
        if not self.gmail_message_id and self.gmail_id:
            self.gmail_message_id = self.gmail_id
        if self.plain_body and not self.body:
            self.body = self.plain_body
        elif self.body and not self.plain_body:
            self.plain_body = self.body
        if self.extracted_deadline and not self.deadline:
            self.deadline = self.extracted_deadline
        elif self.deadline and not self.extracted_deadline:
            self.extracted_deadline = self.deadline

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
