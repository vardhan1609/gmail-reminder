from typing import List, Optional
from pydantic import BaseModel


class NonSecretConfigResponse(BaseModel):
    google_client_id_configured: bool
    google_redirect_uri: str
    poll_interval_seconds: int
    historical_sync_days: int
    dry_run: bool
    notification_mode: str
    digest_interval_minutes: int
    privacy_mode: bool
    notification_cutoff_hours: int
    gmail_include_labels: List[str]
    gmail_exclude_labels: List[str]
    whatsapp_provider: str
    whatsapp_configured: bool
    telegram_configured: bool
    llm_provider_configured: Optional[str] = None
    reminder_offsets_minutes: List[int]

