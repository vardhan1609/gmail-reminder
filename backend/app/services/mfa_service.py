"""
Multi-Factor Authentication (MFA / TOTP) service.
Handles RFC 6238 TOTP enrollment, encrypted secret storage, QR code provisioning,
time-window code verification, single-use hashed recovery code generation and redemption.
"""
from __future__ import annotations

import base64
import hashlib
import io
import secrets
import string
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import pyotp
import qrcode
from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import (
    MFAConfigurationModel,
    RecoveryCodeModel,
    UserModel,
    UserSessionModel,
)
from app.services.auth_service import log_audit_event
from app.utils.crypto import decrypt_data, encrypt_data
from app.utils.logger import get_logger

logger = get_logger(__name__)


def generate_recovery_codes(count: int = 10) -> List[str]:
    """Generate cryptographically secure human-readable recovery codes formatted as XXXX-XXXX."""
    alphabet = string.ascii_lowercase + string.digits
    # Remove easily confused characters: 0, o, 1, l, i
    safe_chars = [c for c in alphabet if c not in ("0", "o", "1", "l", "i")]
    codes = []
    for _ in range(count):
        part1 = "".join(secrets.choice(safe_chars) for _ in range(4))
        part2 = "".join(secrets.choice(safe_chars) for _ in range(4))
        codes.append(f"{part1}-{part2}")
    return codes


def hash_recovery_code(code: str) -> str:
    """Normalize and compute SHA-256 hash of a recovery code."""
    normalized = code.strip().replace("-", "").replace(" ", "").lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def initiate_mfa_enrollment(
    db: Session, user: UserModel
) -> Tuple[str, str, str]:
    """
    Begin TOTP enrollment for a user:
    - Generates a new random Base32 secret
    - Encrypts the secret at rest
    - Generates the otpauth:// URI and base64 QR code PNG
    Returns (secret_base32, provisioning_uri, qr_code_data_url).
    """
    secret = pyotp.random_base32()
    encrypted_secret = encrypt_data(secret)
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.email, issuer_name=settings.mfa_issuer_name
    )

    # Generate QR Code PNG as Data URL
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    qr_data_url = f"data:image/png;base64,{qr_base64}"

    # Upsert MFA configuration
    config = (
        db.query(MFAConfigurationModel)
        .filter(MFAConfigurationModel.user_id == user.id)
        .first()
    )
    now = datetime.now(timezone.utc)
    if not config:
        config = MFAConfigurationModel(
            user_id=user.id,
            encrypted_secret=encrypted_secret,
            is_enabled=False,
            created_at=now,
            updated_at=now,
        )
        db.add(config)
    else:
        config.encrypted_secret = encrypted_secret
        config.is_enabled = False
        config.confirmed_at = None
        config.updated_at = now

    db.commit()
    return secret, provisioning_uri, qr_data_url


def confirm_mfa_enrollment(
    db: Session,
    user: UserModel,
    totp_code: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[bool, Optional[str], List[str]]:
    """
    Confirm TOTP enrollment with a code from authenticator app.
    If valid:
    - Activates MFA on user and configuration
    - Generates 10 single-use recovery codes
    - Hashes recovery codes and saves them to DB
    Returns (success, error_message, plain_recovery_codes).
    """
    config = (
        db.query(MFAConfigurationModel)
        .filter(MFAConfigurationModel.user_id == user.id)
        .first()
    )
    if not config or not config.encrypted_secret:
        return False, "MFA enrollment has not been initiated.", []

    secret = decrypt_data(config.encrypted_secret)
    totp = pyotp.TOTP(secret)

    if not totp.verify(totp_code.strip(), valid_window=1):
        return False, "Invalid authenticator code. Please check your device time and try again.", []

    now = datetime.now(timezone.utc)
    config.is_enabled = True
    config.confirmed_at = now
    config.updated_at = now
    user.mfa_enabled = True
    user.updated_at = now

    # Remove old recovery codes if any
    db.query(RecoveryCodeModel).filter(RecoveryCodeModel.user_id == user.id).delete()

    # Generate 10 new recovery codes
    plain_codes = generate_recovery_codes(10)
    for code in plain_codes:
        code_hash = hash_recovery_code(code)
        rec = RecoveryCodeModel(
            user_id=user.id,
            code_hash=code_hash,
            created_at=now,
        )
        db.add(rec)

    log_audit_event(
        db,
        event_type="mfa_enabled",
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.commit()
    return True, None, plain_codes


def verify_totp_code(db: Session, user: UserModel, totp_code: str) -> bool:
    """Verify a 6-digit TOTP code for a user."""
    config = (
        db.query(MFAConfigurationModel)
        .filter(
            MFAConfigurationModel.user_id == user.id,
            MFAConfigurationModel.is_enabled.is_(True),
        )
        .first()
    )
    if not config or not config.encrypted_secret:
        return False

    secret = decrypt_data(config.encrypted_secret)
    totp = pyotp.TOTP(secret)
    return bool(totp.verify(totp_code.strip(), valid_window=1))


def verify_and_consume_recovery_code(
    db: Session,
    user: UserModel,
    recovery_code: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> bool:
    """Verify and invalidate a single-use recovery code."""
    code_hash = hash_recovery_code(recovery_code)
    now = datetime.now(timezone.utc)

    record = (
        db.query(RecoveryCodeModel)
        .filter(
            RecoveryCodeModel.user_id == user.id,
            RecoveryCodeModel.code_hash == code_hash,
            RecoveryCodeModel.used_at.is_(None),
        )
        .first()
    )
    if not record:
        return False

    record.used_at = now
    log_audit_event(
        db,
        event_type="mfa_recovery_code_used",
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
    return True


def disable_mfa(
    db: Session,
    user: UserModel,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> bool:
    """Disable MFA and invalidate all recovery codes for a user."""
    config = (
        db.query(MFAConfigurationModel)
        .filter(MFAConfigurationModel.user_id == user.id)
        .first()
    )
    now = datetime.now(timezone.utc)
    if config:
        config.is_enabled = False
        config.confirmed_at = None
        config.updated_at = now

    user.mfa_enabled = False
    user.updated_at = now

    # Invalidate recovery codes
    db.query(RecoveryCodeModel).filter(RecoveryCodeModel.user_id == user.id).delete()

    log_audit_event(
        db,
        event_type="mfa_disabled",
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
    return True

