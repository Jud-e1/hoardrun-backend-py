"""
The secret that signs sign-in tokens.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_signing_key.py --noconftest --import-mode=importlib
"""

import os

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
import jwt

from app.auth import signing_key
from app.auth.jwt_handler import JWTHandler

STRONG = "x" * 20 + "a-real-random-looking-secret-value"


@pytest.fixture
def fresh(monkeypatch):
    """Each test chooses its own secret and environment."""
    monkeypatch.setattr(signing_key, "_secret", None)
    settings = signing_key.get_settings()
    monkeypatch.setattr(settings, "jwt_secret_key", "")
    monkeypatch.setattr(settings, "secret_key", "")
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    yield monkeypatch
    signing_key._secret = None


def test_real_secret_is_used(fresh):
    fresh.setenv("JWT_SECRET_KEY", STRONG)
    assert signing_key.jwt_secret() == STRONG


@pytest.mark.parametrize("weak", ["", "your-secret-key-here", "your-secret-key-change-in-production", "short-secret"])
def test_production_refuses_missing_placeholder_or_short_secrets(fresh, weak):
    fresh.setenv("ENVIRONMENT", "production")
    if weak:
        fresh.setenv("JWT_SECRET_KEY", weak)
    with pytest.raises(signing_key.SigningKeyError):
        signing_key.jwt_secret()


def test_development_never_falls_back_to_a_public_default(fresh):
    fresh.setenv("JWT_SECRET_KEY", "your-secret-key-here")
    secret = signing_key.jwt_secret()
    assert secret not in signing_key.PLACEHOLDERS and len(secret) >= signing_key.MIN_LENGTH
    # Stable for the life of the process, so tokens keep working until a restart
    assert signing_key.jwt_secret() == secret


def test_token_forged_with_the_old_public_default_is_rejected(fresh):
    fresh.setenv("JWT_SECRET_KEY", STRONG)
    forged = jwt.encode({"sub": "victim", "type": "access", "exp": 9999999999}, "your-secret-key-change-in-production", algorithm="HS256")
    with pytest.raises(Exception):
        JWTHandler.get_user_id_from_token(forged)


def test_signing_and_checking_use_the_same_secret(fresh):
    fresh.setenv("JWT_SECRET_KEY", STRONG)
    token = JWTHandler.create_access_token({"sub": "ada"})
    assert JWTHandler.get_user_id_from_token(token) == "ada"
