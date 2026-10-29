"""
WhatsApp integration adapter supporting:
- whatsapp-web.js bridge
- Meta Cloud API
- Dry-run mode
- Length limiting (4096 chars)
- Rate limiting and connection error handling
"""
import time
import httpx
from typing import Optional, Tuple

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

MAX_WA_MESSAGE_LENGTH = 4096


class WhatsAppSendError(Exception):
    pass


def format_whatsapp_message(text: str) -> str:
    """Sanitizes text and trims to WhatsApp length limit."""
    if not text:
        return ""
    if len(text) > MAX_WA_MESSAGE_LENGTH:
        return text[: MAX_WA_MESSAGE_LENGTH - 20] + "\n...[truncated]"
    return text


def send_group_message(group_id: str, text: str) -> bool:
    """
    Sends message to configured WhatsApp destination.
    Respects DRY_RUN mode.
    """
    if not group_id:
        group_id = settings.whatsapp_destination

    if not group_id:
        raise WhatsAppSendError("No WhatsApp destination group_id provided")

    formatted_text = format_whatsapp_message(text)

    # Dry-run check
    if settings.dry_run or settings.whatsapp_provider == "dry_run":
        logger.info("[DRY_RUN] WhatsApp notification to %s: %s", group_id, formatted_text[:100])
        return True

    # Meta Cloud API Direct Delivery (1:1 / phone number)
    if settings.whatsapp_provider == "meta" and settings.whatsapp_business_token:
        return _send_via_meta_cloud(group_id, formatted_text)

    # Standard whatsapp-web.js bridge HTTP POST
    url = f"{settings.whatsapp_service_url.rstrip('/')}/send"
    payload = {"groupId": group_id, "message": formatted_text}
    headers = {"Authorization": f"Bearer {settings.whatsapp_service_token}"}

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=20.0)
        if resp.status_code == 429:
            raise WhatsAppSendError("WhatsApp rate limit encountered (429)")
        resp.raise_for_status()
        logger.info("Sent WhatsApp message to %s", group_id)
        return True
    except httpx.ConnectError as exc:
        logger.error("WhatsApp bridge connection failed: %s", exc)
        raise WhatsAppSendError("WhatsApp bridge service unreachable") from exc
    except httpx.HTTPError as exc:
        logger.error("WhatsApp delivery failed: %s", exc)
        raise WhatsAppSendError(str(exc)) from exc


def _send_via_meta_cloud(to_number: str, text: str) -> bool:
    """Direct delivery using official Meta WhatsApp Cloud API."""
    phone_id = settings.whatsapp_phone_number_id
    token = settings.whatsapp_business_token
    if not phone_id or not token:
        raise WhatsAppSendError("Meta WhatsApp credentials not fully configured")

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"preview_url": True, "body": text},
    }

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=20.0)
        resp.raise_for_status()
        logger.info("Sent Meta Cloud WhatsApp message to %s", to_number)
        return True
    except httpx.HTTPError as exc:
        logger.error("Meta Cloud API failed: %s", exc)
        raise WhatsAppSendError(f"Meta Cloud API error: {exc}") from exc


def bridge_is_ready() -> bool:
    """Checks WhatsApp bridge health status."""
    if settings.dry_run or settings.whatsapp_provider == "dry_run":
        return True
    try:
        resp = httpx.get(f"{settings.whatsapp_service_url.rstrip('/')}/health", timeout=5.0)
        return resp.status_code == 200 and resp.json().get("ready", False)
    except Exception:
        return False
