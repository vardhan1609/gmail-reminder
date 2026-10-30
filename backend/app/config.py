"""
Central configuration loaded from environment variables / .env file.
"""
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Google OAuth 2.0
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://127.0.0.1:8000/auth/google/callback"
    google_sso_redirect_uri: str = ""
    google_token_encryption_key: str = ""
    gmail_scopes: str = (
        "https://www.googleapis.com/auth/gmail.readonly "
        "https://www.googleapis.com/auth/calendar.events"
    )
    tokens_dir: str = "tokens"

    # Database: SQLite or PostgreSQL
    database_url: str = "sqlite:///./gmail_reminder.db"
    # Legacy MongoDB fallback settings if used
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "gmail_reminder"

    # Application & Security
    secret_key: str = "change-me-secret-key-production-32-chars-min"
    api_key: Optional[str] = None
    session_cookie_name: str = "session_id"
    session_expiry_days: int = 7
    email_verification_token_expiry_hours: int = 24
    password_reset_token_expiry_hours: int = 1
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cors_allowed_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    frontend_base_url: str = "http://localhost:3000"
    mfa_issuer_name: str = "GmailReminder"
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "text"
    poll_interval_seconds: int = 120
    historical_sync_days: int = 7
    dry_run: bool = False

    # Notification Modes: "immediate", "summary", "important_only"
    notification_mode: str = "immediate"
    digest_interval_minutes: int = 60
    privacy_mode: bool = False
    notification_cutoff_hours: int = 24

    # Gmail Synchronization
    gmail_query: str = ""  # Empty by default so we don't restrict emails
    gmail_include_labels: str = "INBOX"
    gmail_exclude_labels: str = "SENT,SPAM,TRASH,DRAFT"
    include_sent: bool = False
    include_spam: bool = False
    include_trash: bool = False

    # Classification / LLM APIs (optional fallback)
    llm_provider: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20240620"
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = ""

    # Reminders
    reminder_offsets_min: str = "1440,360,60"  # 24h, 6h, 1h

    # WhatsApp Integration
    whatsapp_provider: str = "webjs"  # "webjs", "meta", or "dry_run"
    whatsapp_service_url: str = "http://localhost:3000"
    whatsapp_service_token: str = "change-me"
    whatsapp_destination: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_business_token: str = ""
    whatsapp_verify_token: str = "change-me-webhook"

    # Telegram Integration
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Outlook Calendar (optional)
    outlook_client_id: str = ""
    outlook_client_secret: str = ""
    outlook_tenant_id: str = "common"
    outlook_redirect_uri: str = "http://localhost:8000/calendar/outlook/callback"
    outlook_scopes: str = "Calendars.ReadWrite offline_access User.Read"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_tokens_dir(self) -> Path:
        p = Path(self.tokens_dir)
        if not p.is_absolute():
            return Path(__file__).resolve().parents[2] / p
        return p

    @property
    def reminder_offsets_minutes(self) -> list[int]:
        return [int(x.strip()) for x in self.reminder_offsets_min.split(",") if x.strip()]

    @property
    def included_labels(self) -> list[str]:
        if not self.gmail_include_labels:
            return []
        return [l.strip().upper() for l in self.gmail_include_labels.split(",") if l.strip()]

    @property
    def excluded_labels(self) -> list[str]:
        labels = [l.strip().upper() for l in self.gmail_exclude_labels.split(",") if l.strip()]
        if self.include_sent and "SENT" in labels:
            labels.remove("SENT")
        if self.include_spam and "SPAM" in labels:
            labels.remove("SPAM")
        if self.include_trash and "TRASH" in labels:
            labels.remove("TRASH")
        return labels


settings = Settings()
