"""Encryption of sensitive values at rest (e.g. webhook signing secrets).

Fernet (AES-128-CBC + HMAC-SHA256). The key comes from SECRET_ENCRYPTION_KEY (required in
production); in development it is derived from JWT_SECRET so local setups keep working.
Values written before encryption existed (no prefix) are still readable.
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

PREFIX = "enc:v1:"


@lru_cache
def _fernet() -> Fernet:
    s = get_settings()
    key = s.secret_encryption_key or base64.urlsafe_b64encode(hashlib.sha256(s.jwt_secret.encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt(value: str) -> str:
    return PREFIX + _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    if not value.startswith(PREFIX):
        return value  # legacy plaintext
    try:
        return _fernet().decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Encrypted value cannot be decrypted with the configured key") from exc
