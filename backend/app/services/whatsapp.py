"""
Posts messages to a WhatsApp group via the companion Node service in
`whatsapp-service/` (a thin HTTP wrapper around whatsapp-web.js). One
bridge/session serves any number of groups -- the target group JID is
passed per call (see app/models/destination.py).

IMPORTANT: whatsapp-web.js automates a real personal WhatsApp Web session
and is not an officially sanctioned integration. This is the only way to
post into a *group* (the official Cloud API only supports 1:1 /
business-initiated chats). See README.md for the tradeoffs and the
Telegram alternative (app/services/telegram.py) if you'd rather avoid ToS
risk entirely.
"""
import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WhatsAppSendError(Exception):
    pass


def send_group_message(group_id: str, text: str) -> None:
    if not group_id:
        raise WhatsAppSendError("no group_id provided")

    url = f"{settings.whatsapp_service_url}/send"
    payload = {"groupId": group_id, "message": text}
    headers = {"Authorization": f"Bearer {settings.whatsapp_service_token}"}

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("WhatsApp send failed: %s", exc)
        raise WhatsAppSendError(str(exc)) from exc

    logger.info("Sent WhatsApp message to group %s", group_id)


def bridge_is_ready() -> bool:
    try:
        resp = httpx.get(f"{settings.whatsapp_service_url}/health", timeout=5)
        return resp.status_code == 200 and resp.json().get("ready", False)
    except httpx.HTTPError:
        return False
