from app.services.whatsapp import send_group_message as send_wa, bridge_is_ready as wa_ready, WhatsAppSendError
from app.services.telegram import send_group_message as send_tg, bot_is_ready as tg_ready, TelegramSendError
from app.utils.logger import get_logger

logger = get_logger(__name__)


def destination_is_ready(destination) -> bool:
    """Check connection status for WhatsApp / Telegram integrations."""
    if destination.type == "whatsapp":
        return wa_ready()
    elif destination.type == "telegram":
        return tg_ready()
    return False


def send_notification(destination, message: str) -> tuple[bool, str | None]:
    """
    Route message payload to the correct channel.
    Returns: (success_status, error_message_if_any)
    """
    try:
        if destination.type == "whatsapp":
            send_wa(destination.target_id, message)
            return True, None
        elif destination.type == "telegram":
            send_tg(destination.target_id, message)
            return True, None
    except Exception as exc:
        logger.error("Notification failed for %s (%s): %s", destination.target_id, destination.type, exc)
        return False, str(exc)
    
    return False, f"Unsupported destination type: {destination.type}"
