"""Transactional email delivery for account verification and password recovery."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def send_transactional_email(to_email: str, subject: str, body: str) -> None:
    """Send a plain-text account email using SMTP with TLS.

    SMTP credentials and message content are never logged. Configuration is
    validated at application startup in production.
    """
    if not settings.smtp_host or not settings.smtp_from_email:
        raise RuntimeError("Transactional email is not configured.")

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
    tls_context = ssl.create_default_context()

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=15, context=tls_context
        ) as server:
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls(context=tls_context)
            server.ehlo()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
