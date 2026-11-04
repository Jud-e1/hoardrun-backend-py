"""
Encryption at rest for sensitive columns (bank tokens and account numbers).
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from ..config.settings import get_settings


def _build_fernet() -> Fernet:
    key = os.getenv("DATA_ENCRYPTION_KEY")
    if key:
        try:
            # A Fernet key (Fernet.generate_key()) is used as it is
            return Fernet(key)
        except ValueError:
            # Any other long secret works too, the way services/sealed.py reads the same variable
            if len(key) < 32:
                raise RuntimeError("DATA_ENCRYPTION_KEY must be a Fernet key or 32+ random characters")
            return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode("utf-8")).digest()))

    settings = get_settings()
    if os.getenv("ENVIRONMENT", "").lower() == "production":
        raise RuntimeError("DATA_ENCRYPTION_KEY must be set in production")

    # Development only: derived from the JWT secret so local setups need no extra config
    digest = hashlib.sha256(settings.jwt_secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


_fernet = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = _build_fernet()
    return _fernet


class EncryptedString(TypeDecorator):
    """A string column that is stored encrypted and read back as plain text."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _get_fernet().encrypt(str(value).encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return _get_fernet().decrypt(value.encode()).decode()
