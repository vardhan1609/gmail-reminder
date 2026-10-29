"""
Authentication and session management service.
Handles Argon2id password hashing, opaque session generation, email verification,
password resets, brute force throttling, and audit logging.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import (
    AuditEventModel,
    EmailVerificationTokenModel,
    PasswordResetTokenModel,
    UserModel,
    UserSessionModel,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Argon2id password hasher
_ph = PasswordHasher(
    time_cost=2,
    memory_cost=19456,  # 19 MiB for responsive API while maintaining memory hardness
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

# In-memory failed login tracking for rate limiting / brute force mitigation
_failed_attempts: Dict[str, List[float]] = {}
_failed_lock = threading.Lock()
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 900  # 15 minutes


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against Argon2id hash."""
    try:
        return _ph.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False
    except Exception as exc:
        logger.error("Unexpected error verifying password: %s", exc)
        return False


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that password meets security requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if len(password) > 128:
        return False, "Password must not exceed 128 characters."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[\W_]", password):
        return False, "Password must contain at least one special character."
    return True, None


def check_rate_limit(key: str) -> Tuple[bool, int]:
    """
    Check if a key (e.g. IP or email) has exceeded failed login limits.
    Returns (is_allowed, remaining_cooldown_seconds).
    """
    now = time.time()
    with _failed_lock:
        attempts = _failed_attempts.get(key, [])
        # Filter attempts within the window
        valid_attempts = [t for t in attempts if now - t < LOCKOUT_WINDOW_SECONDS]
        _failed_attempts[key] = valid_attempts

        if len(valid_attempts) >= MAX_FAILED_ATTEMPTS:
            oldest = valid_attempts[0]
            cooldown = int(LOCKOUT_WINDOW_SECONDS - (now - oldest))
            return False, max(1, cooldown)
        return True, 0


def record_failed_attempt(key: str) -> None:
    """Record a failed attempt for rate limiting."""
    now = time.time()
    with _failed_lock:
        if key not in _failed_attempts:
            _failed_attempts[key] = []
        _failed_attempts[key].append(now)


def clear_failed_attempts(key: str) -> None:
    """Clear failed attempts upon successful authentication."""
    with _failed_lock:
        _failed_attempts.pop(key, None)


def log_audit_event(
    db: Session,
    event_type: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AuditEventModel:
    """Record an audit trail event."""
    try:
        details_str = json.dumps(details) if details else None
        event = AuditEventModel(
            user_id=user_id,
            event_type=event_type,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            details=details_str,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    except Exception as exc:
        logger.error("Failed to log audit event %s: %s", event_type, exc)
        db.rollback()
        raise


def create_session(
    db: Session,
    user: UserModel,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    is_mfa_completed: bool = True,
) -> Tuple[UserSessionModel, str]:
    """
    Generate a 256-bit cryptographically secure session token.
    Store only the SHA-256 hash in the database.
    Return (UserSessionModel, raw_token_for_cookie).
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.session_expiry_days)

    session = UserSessionModel(
        user_id=user.id,
        session_token_hash=token_hash,
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
        is_mfa_completed=is_mfa_completed,
        expires_at=expires_at,
        created_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, raw_token


def validate_session(db: Session, raw_token: str) -> Optional[Tuple[UserSessionModel, UserModel]]:
    """
    Validate a raw session token.
    Checks SHA-256 hash, expiration, and user active status.
    Updates last_active_at.
    """
    if not raw_token:
        return None

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    session = (
        db.query(UserSessionModel)
        .filter(UserSessionModel.session_token_hash == token_hash)
        .first()
    )

    if not session:
        return None

    # Handle naive vs timezone-aware datetimes safely
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= now:
        # Expired session
        db.delete(session)
        db.commit()
        return None

    user = db.query(UserModel).filter(UserModel.id == session.user_id).first()
    if not user or not user.is_active:
        return None

    # Sliding expiration / last active update
    session.last_active_at = now
    db.commit()

    return session, user


def disconnect_user_sockets(user_id: str) -> None:
    """Disconnect active WebSocket connections for a user upon session termination."""
    try:
        import asyncio
        from app.websocket.manager import connection_manager
        from app.websocket.publisher import get_main_event_loop
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = get_main_event_loop()
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(connection_manager.disconnect_user(user_id), loop)
    except Exception:
        pass


def revoke_session(db: Session, session_id: str, user_id: str) -> bool:
    """Revoke a specific session."""
    session = (
        db.query(UserSessionModel)
        .filter(UserSessionModel.id == session_id, UserSessionModel.user_id == user_id)
        .first()
    )
    if session:
        db.delete(session)
        db.commit()
        # Check if user has any remaining sessions
        remaining = db.query(UserSessionModel).filter(UserSessionModel.user_id == user_id).count()
        if remaining == 0:
            disconnect_user_sockets(user_id)
        return True
    return False


def revoke_all_user_sessions(
    db: Session, user_id: str, except_session_id: Optional[str] = None
) -> int:
    """Revoke all sessions for a user, optionally keeping the current session."""
    query = db.query(UserSessionModel).filter(UserSessionModel.user_id == user_id)
    if except_session_id:
        query = query.filter(UserSessionModel.id != except_session_id)
    count = query.delete(synchronize_session=False)
    db.commit()
    if not except_session_id:
        disconnect_user_sockets(user_id)
    return count


def create_email_verification_token(db: Session, user_id: str) -> str:
    """Create a short-lived token for email verification."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=settings.email_verification_token_expiry_hours
    )

    token_obj = EmailVerificationTokenModel(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_at=datetime.now(timezone.utc),
    )
    db.add(token_obj)
    db.commit()
    return raw_token


def verify_email_token(db: Session, raw_token: str) -> Optional[UserModel]:
    """Verify email verification token and activate user."""
    if not raw_token:
        return None
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    record = (
        db.query(EmailVerificationTokenModel)
        .filter(
            EmailVerificationTokenModel.token_hash == token_hash,
            EmailVerificationTokenModel.used_at.is_(None),
        )
        .first()
    )
    if not record:
        return None

    exp = record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp <= now:
        return None

    record.used_at = now
    user = db.query(UserModel).filter(UserModel.id == record.user_id).first()
    if user:
        user.is_verified = True
        user.updated_at = now
    db.commit()
    return user


def create_password_reset_token(db: Session, user_id: str) -> str:
    """Create a single-use password reset token."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=settings.password_reset_token_expiry_hours
    )

    token_obj = PasswordResetTokenModel(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_at=datetime.now(timezone.utc),
    )
    db.add(token_obj)
    db.commit()
    return raw_token


def reset_password_with_token(
    db: Session,
    raw_token: str,
    new_password: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Verify reset token, validate new password, update password, and revoke all active sessions."""
    valid, msg = validate_password_strength(new_password)
    if not valid:
        return False, msg

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    record = (
        db.query(PasswordResetTokenModel)
        .filter(
            PasswordResetTokenModel.token_hash == token_hash,
            PasswordResetTokenModel.used_at.is_(None),
        )
        .first()
    )
    if not record:
        return False, "Invalid or expired reset token."

    exp = record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp <= now:
        return False, "Reset token has expired."

    record.used_at = now
    user = db.query(UserModel).filter(UserModel.id == record.user_id).first()
    if not user:
        return False, "User not found."

    user.password_hash = hash_password(new_password)
    user.updated_at = now

    # Invalidate all existing sessions upon password reset
    revoke_all_user_sessions(db, user.id)

    log_audit_event(
        db,
        event_type="password_reset_completed",
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.commit()
    return True, None

