"""
Fixes from the security review (#19): sign-in checks, brute-force limits, token handling and
what production exposes.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_security_review.py --noconftest --import-mode=importlib
"""

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import dependencies, passwords, signing_key
from app.core import auth as core_auth
from app.core.exceptions import AuthenticationException
from app.database import config as db_config
from app.database import registry  # noqa: F401 - every table
from app.database.config import Base
from app.database.models import User
from app.models.auth import UserLoginRequest
from app.services import email_service, login_throttle
from app.services.auth_service import AuthService

GOOD = "Right-Passw0rd"


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    # The checks open their own sessions, so point them at this database
    monkeypatch.setattr(db_config, "SessionLocal", Session)
    monkeypatch.setattr(dependencies, "SessionLocal", Session, raising=False)
    monkeypatch.setattr(email_service, "deliver", lambda *a: True)
    monkeypatch.setattr(email_service, "_pool", type("Now", (), {"submit": staticmethod(lambda fn, *a: fn(*a))})())
    with Session() as session:
        session.add(User(id="ada", email="ada@example.com", password_hash=passwords.hash_password(GOOD),
                         first_name="Ada", last_name="M", status="active", role="user", email_verified=True))
        session.add(User(id="gone", email="gone@example.com", password_hash="x", first_name="G", last_name="X",
                         status="deactivated", role="user"))
        session.commit()
        yield session


def token(sub, **claims):
    body = {"sub": sub, "type": "access", "exp": int((datetime.utcnow() + timedelta(minutes=5)).timestamp()), **claims}
    return jwt.encode(body, signing_key.jwt_secret(), algorithm="HS256")


def check(raw):
    return asyncio.run(core_auth.get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw)))


def login(db, password, email="ada@example.com"):
    return asyncio.run(AuthService().authenticate_user(UserLoginRequest(email=email, password=password), db))


def test_older_routes_refuse_a_closed_account(db):
    assert check(token("ada"))["user_id"] == "ada"
    with pytest.raises(HTTPException) as refused:
        check(token("gone"))
    assert refused.value.status_code == 401


def test_an_admin_claim_in_the_token_is_not_enough(db):
    claims = check(token("ada", role="admin"))
    with pytest.raises(HTTPException) as refused:
        asyncio.run(core_auth.require_admin_user(claims))
    assert refused.value.status_code == 403
    db.get(User, "ada").role = "admin"
    db.commit()
    assert asyncio.run(core_auth.require_admin_user(claims))["user_id"] == "ada"


@pytest.mark.parametrize("forged", [
    lambda: jwt.encode({"sub": "ada", "type": "access"}, None, algorithm="none"),
    lambda: jwt.encode({"sub": "ada", "type": "access"}, signing_key.jwt_secret(), algorithm="HS512"),
    lambda: jwt.encode({"sub": "ada", "type": "access"}, "some-other-secret-that-is-long-enough", algorithm="HS256"),
    lambda: token("ada", type="refresh"),
    lambda: jwt.encode({"sub": "ada", "type": "access", "exp": 1}, signing_key.jwt_secret(), algorithm="HS256"),
])
def test_forged_wrong_algorithm_refresh_and_expired_tokens_are_refused(db, forged):
    with pytest.raises(HTTPException):
        check(forged())


def test_an_unknown_email_looks_exactly_like_a_wrong_password(db):
    with pytest.raises(AuthenticationException) as unknown:
        login(db, GOOD, email="nobody@example.com")
    with pytest.raises(AuthenticationException) as wrong:
        login(db, "Wrong-Passw0rd")
    assert str(unknown.value) == str(wrong.value)


def test_five_wrong_passwords_lock_sign_in_and_a_reset_unlocks_it(db):
    for _ in range(login_throttle.MAX_FAILURES):
        with pytest.raises(AuthenticationException):
            login(db, "Wrong-Passw0rd")
    # Locked: even the right password is refused for now
    with pytest.raises(AuthenticationException) as locked:
        login(db, GOOD)
    assert "Too many wrong passwords" in str(locked.value)
    login_throttle.clear(db, "ada@example.com")
    assert login(db, GOOD).user.id == "ada"


def test_a_right_password_clears_earlier_mistakes(db):
    for _ in range(login_throttle.MAX_FAILURES - 1):
        with pytest.raises(AuthenticationException):
            login(db, "Wrong-Passw0rd")
    login(db, GOOD)
    with pytest.raises(AuthenticationException) as once:
        login(db, "Wrong-Passw0rd")
    assert "Too many" not in str(once.value)


def test_sign_in_routes_have_a_tight_rate_limit():
    from fastapi.testclient import TestClient
    from app.core import middleware
    from app.main import app
    middleware_limit = middleware.SENSITIVE_LIMIT
    with TestClient(app) as client:
        codes = [client.post("/api/v1/auth/login", json={}).status_code for _ in range(middleware_limit + 1)]
    assert codes[:middleware_limit] == [422] * middleware_limit and codes[-1] == 429


def test_production_hides_the_api_map_and_the_older_routes():
    script = (
        "import os; os.environ.update(ENVIRONMENT='production', DATABASE_URL='postgresql://u:p@127.0.0.1:1/x', "
        "JWT_SECRET_KEY='x'*48, DATA_ENCRYPTION_KEY='y'*48)\n"
        "from app.main import app\n"
        "paths = {getattr(r, 'path', '') for r in app.routes}\n"
        "print('docs' if '/docs' in paths or '/openapi.json' in paths else 'no-docs')\n"
        "from fastapi.routing import APIRoute\n"
        "api = [r.path for r in app.routes if isinstance(r, APIRoute)]\n"
        "print('kyc' if any(p.startswith('/api/v1/kyc') for p in api) else 'no-kyc')\n"
        "print('p2p' if any('/p2p' in p for p in api) else 'no-p2p')\n"
    )
    result = subprocess.run([sys.executable, "-W", "ignore", "-c", script], capture_output=True, text=True,
                            cwd=os.getcwd(), env={**os.environ, "PYTHONPATH": os.getcwd()}, timeout=120)
    lines = [line for line in result.stdout.splitlines() if not line.startswith("{")]
    assert lines[-3:] == ["no-docs", "no-kyc", "no-p2p"], result.stdout[-500:] + result.stderr[-500:]
