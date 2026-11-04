"""
Email: sign-up codes, password reset links, and emails about account events. Resend is faked.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_email.py --noconftest --import-mode=importlib
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth as auth_routes
from app.api.v1 import notifications_store
from app.auth import passwords
from app.auth.dependencies import get_current_user_id
from app.database.config import Base, get_db
from app.database.models import User
from app.models.auth import UserRegisterRequest
from app.services import auth_codes, email_service
from app.services.auth_service import AuthService
from app.services.inbox import notify

STRONG = "Better-Passw0rd"


class Outbox(list):
    def to(self, address):
        return [m for m in self if m["to"] == address]


class NowPool:
    """Runs queued emails straight away instead of on a worker thread."""
    def submit(self, fn, *args):
        fn(*args)


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(User(id="ada", email="ada@example.com", password_hash=passwords.hash_password("Old-Passw0rd"),
                    first_name="Ada", last_name="Mensah", status="active", email_verified=True))
        db.add(User(id="kofi", email="kofi@example.com", password_hash="x", first_name="Kofi", last_name="Boateng",
                    status="pending", email_verified=False))
        db.commit()

    sent = Outbox()

    def fake_deliver(to, subject, html_body, text_body):
        sent.append({"to": to, "subject": subject, "html": html_body, "text": text_body})
        return True

    monkeypatch.setattr(email_service, "deliver", fake_deliver)
    monkeypatch.setattr(email_service, "_pool", NowPool())

    app = FastAPI()
    app.include_router(auth_routes.router, prefix="/api/v1")
    app.include_router(notifications_store.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user_id] = lambda: "ada"
    return TestClient(app), Session, sent


def run(coro):
    return asyncio.run(coro)


def code_in(message):
    return re.search(r"\b(\d{6})\b", message["text"]).group(1)


def token_in(message):
    return re.search(r"token=([A-Za-z0-9_\-]+)", message["text"]).group(1)


def test_sign_up_emails_a_code_that_is_only_stored_hashed(env):
    _, Session, sent = env
    with Session() as db:
        run(AuthService().register_user(UserRegisterRequest(
            email="new@example.com", password=STRONG, first_name="Nana", last_name="Owusu", terms_accepted=True), db))
        code = code_in(sent.to("new@example.com")[0])
        user = db.query(User).filter(User.email == "new@example.com").one()
        assert user.email_verification_code is None
        stored = db.query(auth_codes.AuthCode).filter(auth_codes.AuthCode.user_id == user.id).one()
        assert code not in stored.secret_hash
        assert sent.to("new@example.com")[0]["subject"] == f"{code} is your Hoardrun code"


def test_a_code_only_works_with_its_own_email(env):
    client, Session, sent = env
    client.post("/api/v1/auth/resend-verification", json={"email": "kofi@example.com"})
    code = code_in(sent.to("kofi@example.com")[0])
    # Right code, someone else's email: nothing happens
    assert client.post("/api/v1/auth/verify-email", json={"token": code, "email": "ada@example.com"}).status_code == 400
    assert client.post("/api/v1/auth/verify-email", json={"token": code}).status_code == 400
    assert client.post("/api/v1/auth/verify-email", json={"token": code, "email": "kofi@example.com"}).status_code == 200
    with Session() as db:
        kofi = db.get(User, "kofi")
        assert kofi.email_verified and kofi.status == "active"
    # Used once, then gone
    assert client.post("/api/v1/auth/verify-email", json={"token": code, "email": "kofi@example.com"}).status_code == 400


def test_wrong_guesses_run_out(env):
    client, _, sent = env
    client.post("/api/v1/auth/resend-verification", json={"email": "kofi@example.com"})
    code = code_in(sent.to("kofi@example.com")[0])
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(auth_codes.MAX_TRIES):
        client.post("/api/v1/auth/verify-email", json={"token": wrong, "email": "kofi@example.com"})
    response = client.post("/api/v1/auth/verify-email", json={"token": code, "email": "kofi@example.com"})
    assert response.status_code == 400 and "Too many" in response.json()["detail"]


def test_resend_sends_one_code_waits_a_minute_and_never_says_who_has_an_account(env):
    client, Session, sent = env
    first = client.post("/api/v1/auth/resend-verification", json={"email": "kofi@example.com"}).json()
    nobody = client.post("/api/v1/auth/resend-verification", json={"email": "nobody@example.com"}).json()
    assert first["message"] == nobody["message"] and first["data"] == nobody["data"]
    assert len(sent.to("kofi@example.com")) == 1 and sent.to("nobody@example.com") == []
    client.post("/api/v1/auth/resend-verification", json={"email": "kofi@example.com"})
    assert len(sent.to("kofi@example.com")) == 1
    old = code_in(sent.to("kofi@example.com")[0])
    with Session() as db:
        db.query(auth_codes.AuthCode).update({auth_codes.AuthCode.created_at: datetime.utcnow() - timedelta(minutes=2)})
        db.commit()
    client.post("/api/v1/auth/resend-verification", json={"email": "kofi@example.com"})
    new = code_in(sent.to("kofi@example.com")[1])
    if old != new:
        assert client.post("/api/v1/auth/verify-email", json={"token": old, "email": "kofi@example.com"}).status_code == 400
    assert client.post("/api/v1/auth/verify-email", json={"token": new, "email": "kofi@example.com"}).status_code == 200


def test_password_reset_link_works_once_and_tells_the_owner(env):
    client, Session, sent = env
    known = client.post("/api/v1/auth/forgot-password", json={"email": "ada@example.com"}).json()
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}).json()
    assert known == {**unknown, "timestamp": known.get("timestamp")} or known["message"] == unknown["message"]
    assert sent.to("nobody@example.com") == []
    link = sent.to("ada@example.com")[0]
    assert "/reset-password?token=" in link["text"]
    token = token_in(link)

    assert client.get("/api/v1/auth/reset-password/check", params={"token": token}).json()["data"]["valid"] is True
    weak = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "short"})
    assert weak.status_code == 400
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": STRONG}).status_code == 200
    with Session() as db:
        assert passwords.verify_password(STRONG, db.get(User, "ada").password_hash)
    again = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "Another-Passw0rd"})
    assert again.status_code == 400 and "expired or was already used" in again.json()["detail"]
    assert client.get("/api/v1/auth/reset-password/check", params={"token": token}).json()["data"]["valid"] is False
    assert any(m["subject"].startswith("Your password was changed") for m in sent.to("ada@example.com"))


def test_an_expired_reset_link_is_refused(env):
    client, Session, sent = env
    client.post("/api/v1/auth/forgot-password", json={"email": "ada@example.com"})
    token = token_in(sent.to("ada@example.com")[0])
    with Session() as db:
        db.query(auth_codes.AuthCode).update({auth_codes.AuthCode.expires_at: datetime.utcnow() - timedelta(seconds=1)})
        db.commit()
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": STRONG}).status_code == 400
    with Session() as db:
        assert passwords.verify_password("Old-Passw0rd", db.get(User, "ada").password_hash)


def test_event_emails_follow_the_commit_and_the_preference(env):
    client, Session, sent = env
    with Session() as db:
        notify(db, "ada", "transaction", "Money added", "$25.00 is in your account.", link="/home", key="t1", email=True)
        db.rollback()
    assert sent == []
    with Session() as db:
        notify(db, "ada", "transaction", "Money added", "$25.00 is in your account.", link="/home", key="t2", email=True)
        notify(db, "ada", "info", "Goal reached", "Nice.", key="t3")
        db.commit()
    assert [m["subject"] for m in sent] == ["Money added · Hoardrun"]

    assert client.put("/api/v1/notifications/preferences", json={"email": False}).json()["email"] is False
    assert client.get("/api/v1/notifications/preferences").json() == {"email": False, "marketing": False, "security_always": True}
    with Session() as db:
        notify(db, "ada", "transaction", "Money added", "$5.00 is in your account.", key="t4", email=True)
        notify(db, "ada", "security", "Bank linked", "First Platypus Bank is linked.", key="t5")
        db.commit()
    # Email off still gets security notices
    assert [m["subject"] for m in sent][1:] == ["Bank linked · Hoardrun"]


def test_names_and_messages_are_escaped(env):
    subject, page, text = email_service.verification_email("123456", "<script>alert(1)</script>")
    assert "<script>" not in page and "&lt;script&gt;" in page
    assert "123456" in text and "123456" in page


def test_without_a_key_production_never_logs_the_code(monkeypatch, caplog):
    monkeypatch.setattr(email_service.get_settings(), "resend_api_key", "")
    monkeypatch.setenv("ENVIRONMENT", "production")
    subject, page, text = email_service.verification_email("654321")
    with caplog.at_level(logging.WARNING):
        assert email_service.deliver("ada@example.com", subject, page, text) is False
    assert "654321" not in caplog.text
