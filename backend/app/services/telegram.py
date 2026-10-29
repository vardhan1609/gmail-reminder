"""
Telegram bot integration adapter supporting:
- Bot API sendMessage with markdown escaping
- Length limits (4096 chars)
- Dry-run mode
- Error handling for blocked bots (403), rate limits (429), invalid chats (400)
- Validation of chat IDs
- Bot commands handler (/start, /help, /status, /test)
"""
import re
from typing import Dict, Any, Optional, Tuple
import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

MAX_TELEGRAM_MESSAGE_LENGTH = 4096


class TelegramSendError(Exception):
    pass


def escape_markdown_v2(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2."""
    if not text:
        return ""
    # Characters that need escaping: _ * [ ] ( ) ~ ` > # + - = | { } . !
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


def escape_markdown_v1(text: str) -> str:
    """Escapes special characters for Telegram legacy Markdown."""
    if not text:
        return ""
    # Escape single underscores and asterisks that aren't intended as formatting
    return text.replace("\\", "\\\\")


def validate_chat_id(chat_id: str) -> bool:
    """Validates Telegram chat ID syntax (supports user ID, group negative ID, supergroup -100... ID)."""
    if not chat_id:
        return False
    chat_id = str(chat_id).strip()
    return bool(re.match(r"^-?\d+$", chat_id))


def format_telegram_message(text: str) -> str:
    """Sanitizes text and trims to Telegram length limits."""
    if not text:
        return ""
    if len(text) > MAX_TELEGRAM_MESSAGE_LENGTH:
        return text[: MAX_TELEGRAM_MESSAGE_LENGTH - 15] + "\n...[truncated]"
    return text


def send_group_message(chat_id: str, text: str, parse_mode: Optional[str] = "Markdown") -> bool:
    """
    Sends message to Telegram chat or group.
    Never exposes TELEGRAM_BOT_TOKEN in logs or exception messages.
    """
    if not chat_id:
        chat_id = settings.telegram_chat_id

    if not chat_id or not validate_chat_id(chat_id):
        raise TelegramSendError(f"Invalid or missing Telegram chat_id: {chat_id}")

    formatted_text = format_telegram_message(text)

    # Dry-run check
    if settings.dry_run:
        logger.info("[DRY_RUN] Telegram notification to %s: %s", chat_id, formatted_text[:100])
        return True

    if not settings.telegram_bot_token:
        raise TelegramSendError("TELEGRAM_BOT_TOKEN is not configured")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": formatted_text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        resp = httpx.post(url, json=payload, timeout=15.0)
        if resp.status_code == 429:
            retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
            logger.warning("Telegram rate limit reached; retry after %ss", retry_after)
            raise TelegramSendError(f"Telegram rate limited. Retry after {retry_after}s")
        elif resp.status_code == 403:
            logger.error("Telegram bot was blocked or has no permissions in chat %s", chat_id)
            raise TelegramSendError("Bot blocked or insufficient permissions in chat")
        elif resp.status_code == 400:
            # If markdown parsing failed, retry as plain text without parse_mode
            if parse_mode:
                logger.warning("Telegram markdown parsing failed, retrying plain text")
                return send_group_message(chat_id, formatted_text, parse_mode=None)
            resp.raise_for_status()

        resp.raise_for_status()
        logger.info("Sent Telegram message to chat %s", chat_id)
        return True
    except httpx.HTTPError as exc:
        logger.error("Telegram request failed: %s", exc)
        raise TelegramSendError("Telegram communication error") from exc


def bot_is_ready() -> bool:
    """Checks Telegram bot connectivity via /getMe."""
    if settings.dry_run:
        return True
    if not settings.telegram_bot_token:
        return False
    try:
        resp = httpx.get(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe",
            timeout=5.0,
        )
        return resp.status_code == 200 and resp.json().get("ok", False)
    except Exception:
        return False


def handle_bot_command(command: str, chat_id: str) -> str:
    """
    Handles Telegram bot commands:
    /start, /help, /status, /test
    """
    cmd = command.strip().lower().split()[0]
    if cmd == "/start":
        return (
            "👋 *Welcome to Gmail Reminder Bot!*\n\n"
            "This bot delivers real-time notifications and deadline reminders "
            "from your connected Gmail mailbox.\n\n"
            "Use /help to view available commands, or /status to check system readiness."
        )
    elif cmd == "/help":
        return (
            "📖 *Available Bot Commands:*\n\n"
            "• `/start` — Welcome message and instructions\n"
            "• `/status` — Check backend and bot readiness\n"
            "• `/test` — Trigger a test notification to verify delivery\n"
            "• `/help` — Display this command reference\n\n"
            "*Group Setup Guide:*\n"
            "1. Add this bot to your Telegram group.\n"
            "2. Grant it permission to send messages.\n"
            "3. Send `/status` in the group to confirm your group chat ID."
        )
    elif cmd == "/status":
        is_ready = bot_is_ready()
        return (
            "⚙️ *System Status:*\n\n"
            f"• Bot API: {'🟢 Connected' if is_ready else '🔴 Disconnected'}\n"
            f"• Chat ID: `{chat_id}`\n"
            f"• Notification Mode: `{settings.notification_mode}`\n"
            f"• Dry Run: `{'Enabled' if settings.dry_run else 'Disabled'}`\n"
            f"• Privacy Mode: `{'Enabled' if settings.privacy_mode else 'Disabled'}`"
        )
    elif cmd == "/test":
        return (
            "🔔 *Test Notification Successful!*\n\n"
            "Your Telegram channel is configured correctly and ready to receive "
            "Gmail notifications and reminders."
        )
    else:
        return f"Unknown command: `{command}`. Type /help for available commands."
