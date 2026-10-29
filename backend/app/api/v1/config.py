"""
Config API endpoints (v1).
"""
from fastapi import APIRouter, Depends

from app.config import settings
from app.middleware.auth import require_api_key
from app.schemas.config import NonSecretConfigResponse

router = APIRouter(prefix="/config", tags=["Configuration V1"])


@router.get("", response_model=NonSecretConfigResponse, dependencies=[Depends(require_api_key)])
def get_non_secret_config():
    """Retrieve application configuration parameters without exposing sensitive secrets or credentials."""
    return NonSecretConfigResponse(
        google_client_id_configured=bool(settings.google_client_id and settings.google_client_id != "your-google-client-id"),
        google_redirect_uri=settings.google_redirect_uri,
        poll_interval_seconds=settings.poll_interval_seconds,
        historical_sync_days=settings.historical_sync_days,
        dry_run=settings.dry_run,
        notification_mode=settings.notification_mode,
        digest_interval_minutes=settings.digest_interval_minutes,
        privacy_mode=settings.privacy_mode,
        notification_cutoff_hours=settings.notification_cutoff_hours,
        gmail_include_labels=settings.included_labels,
        gmail_exclude_labels=settings.excluded_labels,
        whatsapp_provider=settings.whatsapp_provider,
        whatsapp_configured=bool(settings.whatsapp_destination or settings.whatsapp_service_url),
        telegram_configured=bool(settings.telegram_bot_token and settings.telegram_chat_id),
        llm_provider_configured=settings.llm_provider if settings.llm_provider else None,
        reminder_offsets_minutes=settings.reminder_offsets_minutes,
    )

