"""
Central configuration, loaded from environment variables / .env file.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Gmail OAuth (shared app credentials; each mailbox gets its own token
    # file once connected via /accounts/gmail/login)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/accounts/gmail/callback"
    # Requesting calendar.events alongside gmail.readonly at connect time
    # means a connected mailbox can optionally push deadlines to its own
    # Google Calendar with no extra consent screen later.
    gmail_scopes: str = (
        "https://www.googleapis.com/auth/gmail.readonly "
        "https://www.googleapis.com/auth/calendar.events"
    )
    tokens_dir: str = "tokens"

    # App — MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "gmail_reminder"

    secret_key: str = "change-me"
    log_level: str = "INFO"
    poll_interval_seconds: int = 120
    gmail_query: str = "is:unread category:primary newer_than:7d"

    # Classification / extraction / LLM APIs
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

    # WhatsApp bridge (shared across both modes)
    whatsapp_service_url: str = "http://localhost:3000"
    whatsapp_service_token: str = "change-me"

    # WhatsApp API mode: "webjs" (whatsapp-web.js, groups) or "meta" (Cloud API, 1:1)
    whatsapp_api_mode: str = "webjs"

    # Meta Cloud API (only used when whatsapp_api_mode == "meta")
    whatsapp_phone_number_id: str = ""
    whatsapp_business_token: str = ""
    whatsapp_verify_token: str = "change-me-webhook"

    # Telegram bot (one bot, posts into any chat/group ID it's a member of)
    telegram_bot_token: str = ""

    # Outlook / Microsoft Graph calendar (single connected calendar, shared
    # across all accounts -- see README for why this isn't per-Gmail-account)
    outlook_client_id: str = ""
    outlook_client_secret: str = ""
    outlook_tenant_id: str = "common"
    outlook_redirect_uri: str = "http://localhost:8000/calendar/outlook/callback"
    outlook_scopes: str = "Calendars.ReadWrite offline_access User.Read"

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    @property
    def resolved_tokens_dir(self) -> Path:
        p = Path(self.tokens_dir)
        if not p.is_absolute():
            return Path(__file__).resolve().parents[2] / p
        return p

    @property
    def reminder_offsets_minutes(self) -> list[int]:
        return [int(x.strip()) for x in self.reminder_offsets_min.split(",") if x.strip()]


settings = Settings()
