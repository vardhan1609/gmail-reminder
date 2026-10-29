"""
Multi-Tenant SQLAlchemy Database Models:
- User, UserSession, EmailVerificationToken, PasswordResetToken
- MFAConfiguration, RecoveryCode
- GmailConnection, NotificationIntegration, NotificationPreferences, AuditEvent
- Email, Reminder, NotificationDelivery, SyncState, Account, Destination, RoutingRule, CalendarEvent
"""
from datetime import datetime, timezone
import json
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Boolean,
    Integer,
    Float,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_verified = Column(Boolean, nullable=False, default=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    is_admin = Column(Boolean, nullable=False, default=False)
    mfa_enabled = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    sessions = relationship("UserSessionModel", back_populates="user", cascade="all, delete-orphan")
    verification_tokens = relationship("EmailVerificationTokenModel", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetTokenModel", back_populates="user", cascade="all, delete-orphan")
    mfa_config = relationship("MFAConfigurationModel", back_populates="user", uselist=False, cascade="all, delete-orphan")
    recovery_codes = relationship("RecoveryCodeModel", back_populates="user", cascade="all, delete-orphan")
    gmail_connections = relationship("GmailConnectionModel", back_populates="user", cascade="all, delete-orphan")
    integrations = relationship("NotificationIntegrationModel", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("NotificationPreferencesModel", back_populates="user", uselist=False, cascade="all, delete-orphan")
    emails = relationship("EmailModel", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "is_verified": self.is_verified,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "mfa_enabled": self.mfa_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UserSessionModel(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token_hash = Column(String(64), unique=True, nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    is_mfa_completed = Column(Boolean, nullable=False, default=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_active_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    user = relationship("UserModel", back_populates="sessions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "is_mfa_completed": self.is_mfa_completed,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
        }


class EmailVerificationTokenModel(Base):
    __tablename__ = "email_verification_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    user = relationship("UserModel", back_populates="verification_tokens")


class PasswordResetTokenModel(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    user = relationship("UserModel", back_populates="password_reset_tokens")


class MFAConfigurationModel(Base):
    __tablename__ = "mfa_configurations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    encrypted_secret = Column(Text, nullable=False)
    is_enabled = Column(Boolean, nullable=False, default=False, index=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    user = relationship("UserModel", back_populates="mfa_config")


class RecoveryCodeModel(Base):
    __tablename__ = "recovery_codes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = Column(String(64), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    user = relationship("UserModel", back_populates="recovery_codes")


class GmailConnectionModel(Base):
    __tablename__ = "gmail_connections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    label = Column(String(255), nullable=True)
    token_path = Column(String(500), nullable=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    history_id = Column(String(100), nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_status = Column(String(100), default="idle")
    calendar_sync_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    user = relationship("UserModel", back_populates="gmail_connections")

    __table_args__ = (
        UniqueConstraint("user_id", "email", name="uq_user_gmail_email"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email": self.email,
            "label": self.label,
            "active": self.active,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "last_sync_status": self.last_sync_status,
            "calendar_sync_enabled": self.calendar_sync_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NotificationIntegrationModel(Base):
    __tablename__ = "notification_integrations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)  # whatsapp, telegram
    name = Column(String(255), nullable=False)
    target_id = Column(String(255), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    user = relationship("UserModel", back_populates="integrations")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "name": self.name,
            "target_id": self.target_id,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NotificationPreferencesModel(Base):
    __tablename__ = "notification_preferences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    notification_mode = Column(String(50), nullable=False, default="immediate")  # immediate, summary, important_only
    digest_interval_minutes = Column(Integer, nullable=False, default=60)
    privacy_mode = Column(Boolean, nullable=False, default=False)
    notification_cutoff_hours = Column(Integer, nullable=False, default=24)
    reminder_offsets_min = Column(String(100), nullable=False, default="1440,360,60")
    included_categories = Column(Text, nullable=True)  # JSON list
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    user = relationship("UserModel", back_populates="preferences")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "notification_mode": self.notification_mode,
            "digest_interval_minutes": self.digest_interval_minutes,
            "privacy_mode": self.privacy_mode,
            "notification_cutoff_hours": self.notification_cutoff_hours,
            "reminder_offsets_min": self.reminder_offsets_min,
            "included_categories": json.loads(self.included_categories) if self.included_categories else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "details": json.loads(self.details) if self.details else {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ─── Multi-Tenant Application Core Data Models ───

def _format_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


class EmailModel(Base):
    __tablename__ = "emails"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    account_id = Column(String(36), nullable=True, index=True)
    gmail_message_id = Column(String(100), unique=True, nullable=False, index=True)
    gmail_thread_id = Column(String(100), nullable=True, index=True)
    sender = Column(String(255), nullable=False)
    recipients = Column(Text, nullable=True)
    subject = Column(String(500), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=True, index=True)
    category = Column(String(100), nullable=False, default="Other", index=True)
    extracted_deadline = Column(DateTime(timezone=True), nullable=True, index=True)
    confidence_score = Column(Float, nullable=True, default=0.0)
    ambiguous_date = Column(Boolean, nullable=False, default=False)
    plain_body = Column(Text, nullable=True)
    html_body = Column(Text, nullable=True)
    attachments_meta = Column(Text, nullable=True)
    labels = Column(Text, nullable=True)
    processing_status = Column(String(50), nullable=False, default="pending", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    user = relationship("UserModel", back_populates="emails")
    reminders = relationship("ReminderModel", back_populates="email", cascade="all, delete-orphan")
    deliveries = relationship("NotificationDeliveryModel", back_populates="email", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_emails_sender_subject", "sender", "subject"),
        Index("ix_emails_user_created", "user_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "gmail_message_id": self.gmail_message_id,
            "gmail_id": self.gmail_message_id,
            "gmail_thread_id": self.gmail_thread_id,
            "sender": self.sender,
            "recipients": self.recipients,
            "subject": self.subject,
            "received_at": _format_utc_iso(self.received_at),
            "category": self.category,
            "extracted_deadline": _format_utc_iso(self.extracted_deadline),
            "deadline": _format_utc_iso(self.extracted_deadline),
            "confidence_score": self.confidence_score,
            "ambiguous_date": self.ambiguous_date,
            "plain_body": self.plain_body,
            "body": self.plain_body,
            "html_body": self.html_body,
            "attachments_meta": self.attachments_meta,
            "labels": self.labels,
            "processing_status": self.processing_status,
            "processed": self.processing_status == "completed",
            "created_at": _format_utc_iso(self.created_at),
            "updated_at": _format_utc_iso(self.updated_at),
        }


class ReminderModel(Base):
    __tablename__ = "reminders"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    email_id = Column(String(36), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True)
    destination_id = Column(String(36), nullable=False, index=True)
    message = Column(Text, nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending", index=True)  # pending, sent, failed
    retry_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    email = relationship("EmailModel", back_populates="reminders")

    __table_args__ = (
        Index("ix_reminders_status_scheduled", "status", "scheduled_at"),
        Index("ix_reminders_user_status", "user_id", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email_id": self.email_id,
            "destination_id": self.destination_id,
            "message": self.message,
            "scheduled_at": _format_utc_iso(self.scheduled_at),
            "reminder_time": _format_utc_iso(self.scheduled_at),
            "status": self.status,
            "retry_count": self.retry_count,
            "retries": self.retry_count,
            "last_error": self.last_error,
            "sent_at": _format_utc_iso(self.sent_at),
            "created_at": _format_utc_iso(self.created_at),
        }


class NotificationDeliveryModel(Base):
    __tablename__ = "notification_deliveries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    email_id = Column(String(36), ForeignKey("emails.id", ondelete="SET NULL"), nullable=True, index=True)
    channel = Column(String(50), nullable=False, index=True)  # whatsapp, telegram
    destination_id = Column(String(255), nullable=False, index=True)
    notification_type = Column(String(50), nullable=False, default="immediate")
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    email = relationship("EmailModel", back_populates="deliveries")

    __table_args__ = (
        Index("ix_deliveries_channel_status", "channel", "status"),
        Index("ix_deliveries_user_created", "user_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email_id": self.email_id,
            "channel": self.channel,
            "destination_id": self.destination_id,
            "notification_type": self.notification_type,
            "idempotency_key": self.idempotency_key,
            "status": self.status,
            "attempts": self.attempts,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SyncStateModel(Base):
    __tablename__ = "sync_states"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    account_identifier = Column(String(255), unique=True, nullable=False, index=True)
    history_id = Column(String(100), nullable=True)
    last_successful_sync = Column(DateTime(timezone=True), nullable=True)
    last_sync_status = Column(String(50), nullable=False, default="idle")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "account_identifier": self.account_identifier,
            "history_id": self.history_id,
            "last_successful_sync": self.last_successful_sync.isoformat() if self.last_successful_sync else None,
            "last_sync_status": self.last_sync_status,
        }


class AccountModel(Base):
    __tablename__ = "accounts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    label = Column(String(255), nullable=True)
    token_path = Column(String(500), nullable=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    calendar_sync_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email": self.email,
            "label": self.label,
            "token_path": self.token_path,
            "active": self.active,
            "calendar_sync_enabled": self.calendar_sync_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DestinationModel(Base):
    __tablename__ = "destinations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    type = Column(String(50), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    target_id = Column(String(255), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "name": self.name,
            "target_id": self.target_id,
            "is_default": self.is_default,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RoutingRuleModel(Base):
    __tablename__ = "routing_rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    account_id = Column(String(36), nullable=True, index=True)
    category = Column(String(100), nullable=True, index=True)
    destination_id = Column(String(36), ForeignKey("destinations.id", ondelete="CASCADE"), nullable=False, index=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "category": self.category,
            "destination_id": self.destination_id,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CalendarEventModel(Base):
    __tablename__ = "calendar_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    email_id = Column(String(36), nullable=False, index=True)
    provider = Column(String(50), nullable=False, index=True)
    external_event_id = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("ix_calendar_email_provider", "email_id", "provider"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email_id": self.email_id,
            "provider": self.provider,
            "external_event_id": self.external_event_id,
            "status": self.status,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
