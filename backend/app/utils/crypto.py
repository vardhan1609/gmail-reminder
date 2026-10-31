"""
Cryptographic utilities for protecting OAuth tokens and sensitive data at rest.
"""
import base64
import hashlib
import os
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_fernet_instance: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    key = settings.google_token_encryption_key or settings.secret_key
    if not key or key.lower().startswith("change-me"):
        raise RuntimeError("A strong GOOGLE_TOKEN_ENCRYPTION_KEY or SECRET_KEY must be configured.")

    # HKDF separates the token-encryption key from other application-secret uses.
    derived_bytes = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"gmail-reminder-token-encryption-v1",
        info=b"oauth-token-at-rest",
    ).derive(key.encode("utf-8"))
    fernet_key = base64.urlsafe_b64encode(derived_bytes)
    try:
        _fernet_instance = Fernet(fernet_key)
        return _fernet_instance
    except Exception as exc:
        logger.error("Could not initialize token encryption.")
        raise RuntimeError("OAuth token encryption could not be initialized.") from exc


def encrypt_data(plaintext: str) -> str:
    """Encrypt with the versioned HKDF-derived Fernet key; never persist plaintext on failure."""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_data(ciphertext: str) -> str:
    """Decrypt new HKDF ciphertexts and legacy SHA-256 ciphertexts during key migration."""
    if not ciphertext.startswith("gAAAA"):
        # Explicit compatibility for historical plaintext JSON tokens.
        return ciphertext
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Read-only fallback for tokens encrypted by the previous SHA-256 derivation.
        # Try both configured secrets because deployments may have moved from the
        # application secret to a dedicated encryption secret during migration.
        legacy_candidates = {
            value for value in (settings.google_token_encryption_key, settings.secret_key)
            if value and not value.lower().startswith("change-me")
        }
        for legacy_secret in legacy_candidates:
            legacy_key = base64.urlsafe_b64encode(
                hashlib.sha256(legacy_secret.encode("utf-8")).digest()
            )
            try:
                return Fernet(legacy_key).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
            except InvalidToken:
                continue
        logger.error("Stored OAuth token could not be decrypted with current or legacy keys.")
        raise ValueError("Stored OAuth token cannot be decrypted; verify configured encryption keys.")


def save_secure_token(token_path: Path, token_json: str) -> None:
    """Save token with encryption at rest."""
    encrypted = encrypt_data(token_json)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(encrypted, encoding="utf-8")


def load_secure_token(token_path: Path) -> Optional[str]:
    """Read token and decrypt if encrypted."""
    if not token_path.exists():
        return None
    content = token_path.read_text(encoding="utf-8")
    return decrypt_data(content)

