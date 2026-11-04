"""
Password hashing and checking.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_passwords.py --noconftest --import-mode=importlib
"""

import os

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import bcrypt

from app.auth import passwords
from app.auth.jwt_handler import JWTHandler
from app.services.auth_service import AuthService


def test_hash_and_check():
    stored = passwords.hash_password("Correct-Horse-9")
    assert stored.startswith("$2b$")
    assert passwords.verify_password("Correct-Horse-9", stored)
    assert not passwords.verify_password("correct-horse-9", stored)


def test_plain_text_stored_passwords_never_match():
    assert not passwords.verify_password("hunter2", "hunter2")
    assert not passwords.verify_password("", "")
    assert not passwords.verify_password("anything", "")


def test_malformed_hash_is_a_failed_check_not_a_crash():
    assert not passwords.verify_password("x", "$2b$12$not-a-real-hash")


def test_long_passwords_work():
    long = "p" * 100 + "€" * 10
    stored = passwords.hash_password(long)
    assert passwords.verify_password(long, stored)


def test_older_50_byte_hashes_still_sign_in():
    long = "a" * 60
    legacy = bcrypt.hashpw(long.encode()[:50], bcrypt.gensalt()).decode()
    assert passwords.verify_password(long, legacy)
    # The fallback is only for long passwords, never a shortcut for short ones
    short_legacy = bcrypt.hashpw(b"short", bcrypt.gensalt()).decode()
    assert not passwords.verify_password("shortX", short_legacy)


def test_every_caller_uses_the_same_rules():
    stored = passwords.hash_password("Same-Rules-1")
    service = AuthService.__new__(AuthService)
    assert JWTHandler.verify_password("Same-Rules-1", stored)
    assert service._verify_password("Same-Rules-1", stored)
    assert passwords.verify_password("Same-Rules-1", JWTHandler.hash_password("Same-Rules-1"))
    assert passwords.verify_password("Same-Rules-1", service._hash_password("Same-Rules-1"))
    # The sign-in and admin sign-in path used to accept a plain-text stored password
    assert not service._verify_password("letmein", "letmein")
    assert not JWTHandler.verify_password("letmein", "letmein")
