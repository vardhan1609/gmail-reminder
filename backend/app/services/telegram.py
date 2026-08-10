"""
Posts messages to a Telegram group via the Bot API. Unlike WhatsApp, this
needs no browser automation and carries no ToS risk: create a bot with
@BotFather, add it to your group, and it can post immediately.

To find a group's chat_id: add the bot to the group, send any message in
the group, then GET https://api.telegram.org/bot<token>/getUpdates and
read `message.chat.id` (it will be a negative number for groups).
"""
import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramSendError(Exception):
    pass


def send_group_message(chat_id: str, text: str) -> None:
    if not settings.telegram_bot_token:
        raise TelegramSendError("TELEGRAM_BOT_TOKEN is not configured")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

    try:
        resp = httpx.post(url, json=payload, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Telegram send failed: %s", exc)
        raise TelegramSendError(str(exc)) from exc

    logger.info("Sent Telegram message to chat %s", chat_id)


def bot_is_ready() -> bool:
    if not settings.telegram_bot_token:
        return False
    try:
        resp = httpx.get(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe", timeout=5
        )
        return resp.status_code == 200 and resp.json().get("ok", False)
    except httpx.HTTPError:
        return False
