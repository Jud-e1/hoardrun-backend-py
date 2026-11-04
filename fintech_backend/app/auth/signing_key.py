"""
The one secret that signs and checks sign-in tokens.

Anyone who knows it can forge a token for any account, so a missing, placeholder or short
secret stops the app from starting in production. In development a random secret is used
for the life of the process instead of a public default (sign-ins then reset on restart).
"""

import logging
import os
import secrets

from ..config.settings import get_settings

logger = logging.getLogger(__name__)

MIN_LENGTH = 32
# Defaults that have appeared in this codebase or its examples; never acceptable as a real secret
# Sign-in tokens are always HMAC-SHA256; the algorithm is never taken from settings or the token
ALGORITHM = "HS256"

PLACEHOLDERS = {
    "", "your-secret-key-here", "your-secret-key-change-in-production", "your-jwt-secret-key",
    "changeme", "change-me", "secret", "jwt-secret",
}

_secret = None


class SigningKeyError(RuntimeError):
    pass


def is_production() -> bool:
    return (os.getenv("ENVIRONMENT") or get_settings().environment or "").strip().lower() == "production"


def is_acceptable(value: str) -> bool:
    return value.strip() not in PLACEHOLDERS and len(value) >= MIN_LENGTH


def jwt_secret() -> str:
    global _secret
    if _secret is not None:
        return _secret
    settings = get_settings()
    candidate = os.getenv("JWT_SECRET_KEY") or settings.jwt_secret_key or settings.secret_key or ""
    if not is_acceptable(candidate):
        if is_production():
            raise SigningKeyError(
                "JWT_SECRET_KEY must be a random value of at least 32 characters in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        logger.warning("JWT_SECRET_KEY is missing or too weak; using a random secret until the server restarts")
        candidate = secrets.token_urlsafe(48)
    _secret = candidate
    return _secret
