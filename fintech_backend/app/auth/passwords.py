"""
Password hashing, in one place.

Uses the bcrypt library directly: passlib 1.7.4 breaks with bcrypt 4.1 and later.
A stored value that isn't a bcrypt hash never matches; passwords are never compared as plain text.
"""

import bcrypt

# bcrypt reads at most 72 bytes of a password
MAX_BYTES = 72
BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def _secret(password: str, limit: int = MAX_BYTES) -> bytes:
    return password.encode("utf-8")[:limit]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_secret(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    if not password or not stored_hash or not stored_hash.startswith(BCRYPT_PREFIXES):
        return False
    try:
        stored = stored_hash.encode("utf-8")
        if bcrypt.checkpw(_secret(password), stored):
            return True
        # Some older accounts were hashed from the first 50 bytes; only differs for long passwords
        return len(password.encode("utf-8")) > 50 and bcrypt.checkpw(_secret(password, 50), stored)
    except ValueError:
        # A malformed hash is a failed check, not a crash
        return False
