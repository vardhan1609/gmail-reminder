"""
Cryptographic utilities for protecting OAuth tokens and sensitive data at rest.
"""
import base64
import hashlib
import os
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_fernet_instance: Optional[Fernet] = None


def _get_fernet() -> Optional[Fernet]:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    key = settings.google_token_encryption_key or settings.secret_key
    if not key:
        key = "default-insecure-encryption-key-for-dev"

    # Derive 32 url-safe base64-encoded bytes from key
    derived_bytes = hashlib.sha256(key.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(derived_bytes)
    try:
        _fernet_instance = Fernet(fernet_key)
        return _fernet_instance
    except Exception as exc:
        logger.warning("Could not initialize token encryption: %s", exc)
        return None


def encrypt_data(plaintext: str) -> str:
    """Encrypt a string payload using Fernet symmetric encryption."""
    fernet = _get_fernet()
    if not fernet:
        return plaintext
    encrypted = fernet.encrypt(plaintext.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_data(ciphertext: str) -> str:
    """Decrypt a ciphertext string back to plaintext. Falls back gracefully if unencrypted."""
    fernet = _get_fernet()
    if not fernet:
        return ciphertext
    try:
        decrypted = fernet.decrypt(ciphertext.encode("utf-8"))
        return decrypted.decode("utf-8")
    except Exception:
        # If it's already plaintext (e.g. from before encryption was enabled), return as-is
        return ciphertext


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

