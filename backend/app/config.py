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

    # Subscription pricing (monthly; integer minor currency units, e.g. paise for INR)
    payment_currency: str = "INR"
    basic_plan_price_paise: int = 0
    premium_plan_price_paise: int = 0

    # Payment provider selection: razorpay or cashfree
    payment_provider: str = "razorpay"
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    cashfree_app_id: str = ""
    cashfree_secret_key: str = ""
    cashfree_webhook_secret: str = ""
    cashfree_environment: str = "sandbox"
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
    environment: str = "development"
    secret_key: str = "change-me-secret-key-production-32-chars-min"
    api_key: Optional[str] = None
    session_cookie_name: str = "session_id"
    session_expiry_days: int = 7
    email_verification_token_expiry_hours: int = 24
    password_reset_token_expiry_hours: int = 1
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_ssl: bool = False
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
    whatsapp_service_url: str = "http://127.0.0.1:3000"
    whatsapp_service_token: str = ""
    whatsapp_destination: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_business_token: str = ""
    whatsapp_verify_token: str = ""

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

    def validate_security_settings(self) -> None:
        """Reject unsafe production configuration before opening the API."""
        if self.environment.lower() not in {"production", "prod"}:
            return
        placeholders = ("change-me", "changeme", "generate-", "your-", "replace-me", "example")
        required_secrets = {
            "SECRET_KEY": self.secret_key,
            "GOOGLE_TOKEN_ENCRYPTION_KEY": self.google_token_encryption_key,
            "WHATSAPP_SERVICE_TOKEN": self.whatsapp_service_token,
            "API_KEY": self.api_key or "",
        }
        invalid = [
            name for name, value in required_secrets.items()
            if len(value.strip()) < 32 or value.strip().lower().startswith(placeholders)
        ]
        if invalid:
            raise RuntimeError("Production requires strong, unique secrets for: " + ", ".join(invalid))
        if not self.cookie_secure:
            raise RuntimeError("COOKIE_SECURE must be true in production.")
        if not self.cors_allowed_origins or any(
            origin.lower().startswith(("http://localhost", "http://127.0.0.1", "https://localhost", "https://127.0.0.1"))
            or not origin.lower().startswith("https://")
            for origin in self.cors_allowed_origins
        ):
            raise RuntimeError("Production CORS_ALLOWED_ORIGINS must contain only explicit HTTPS origins.")
        if not (self.smtp_host and self.smtp_from_email):
            raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL are required in production for account verification and password reset.")
        if self.whatsapp_provider == "webjs" and len(self.whatsapp_service_token) < 32:
            raise RuntimeError("WHATSAPP_SERVICE_TOKEN must be at least 32 characters.")

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
