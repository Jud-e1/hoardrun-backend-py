"""
Encryption for secrets Hoardrun has to keep, such as Plaid access tokens.

The key comes from DATA_ENCRYPTION_KEY. Production refuses to seal or open anything
without one. In development it falls back to SECRET_KEY, so stored tokens survive restarts.
"""

import base64
import hashlib
import logging
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken

from ..auth.signing_key import is_production
from ..config.settings import get_settings

logger = logging.getLogger(__name__)

MIN_LENGTH = 32
_fernet = None


class SealError(RuntimeError):
    pass


def _key_material() -> str:
    settings = get_settings()
    key = os.getenv("DATA_ENCRYPTION_KEY") or settings.data_encryption_key
    if key and len(key) >= MIN_LENGTH:
        return key
    if is_production():
        raise SealError("DATA_ENCRYPTION_KEY must be set to 32 or more random characters in production")
    fallback = os.getenv("SECRET_KEY") or settings.secret_key
    if fallback and len(fallback) >= MIN_LENGTH:
        return "dev-seal:" + fallback
    logger.warning("No DATA_ENCRYPTION_KEY or SECRET_KEY; stored secrets won't survive a restart")
    return secrets.token_urlsafe(48)


def _box() -> Fernet:
    global _fernet
    if _fernet is None:
        digest = hashlib.sha256(_key_material().encode("utf-8")).digest()
        _fernet = Fernet(base64.urlsafe_b64encode(digest))
    return _fernet


def seal(text: str) -> str:
    return _box().encrypt(text.encode("utf-8")).decode("ascii")


def unseal(token: str) -> str:
    try:
        return _box().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        raise SealError("This secret was sealed with a different key")
