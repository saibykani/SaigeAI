"""Symmetric encryption for third-party OAuth tokens at rest (AES-256-GCM).

Key: TOKEN_ENCRYPTION_KEY (urlsafe base64, 32 bytes) if set, otherwise derived from JWT_SECRET
with HKDF so a deployment always has a stable key without extra configuration.
"""

import base64
import os
from functools import lru_cache

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import get_settings


@lru_cache
def _key() -> bytes:
    explicit = os.environ.get("TOKEN_ENCRYPTION_KEY")
    if explicit:
        key = base64.urlsafe_b64decode(explicit + "=" * (-len(explicit) % 4))
        if len(key) != 32:
            raise ValueError("TOKEN_ENCRYPTION_KEY must decode to 32 bytes")
        return key
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=b"saige-ai/token-encryption",
                info=b"oauth-refresh-tokens").derive(get_settings().jwt_secret.encode())


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(_key()).encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ct).decode()


def decrypt(token: str) -> str:
    raw = base64.urlsafe_b64decode(token)
    return AESGCM(_key()).decrypt(raw[:12], raw[12:], None).decode()
