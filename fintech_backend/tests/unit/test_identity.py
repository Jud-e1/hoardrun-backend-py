"""
Identity checks with Persona. Persona's API is faked; webhook signatures use the real check.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_identity.py --noconftest --import-mode=importlib
"""

import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qs, urlparse

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import identity
from app.auth.dependencies import get_current_user_id
from app.database.config import Base, get_db
from app.database.models import User
from app.services import email_service
from app.services.inbox import Notification

SECRET = "wbhsec_test_secret"


class FakePersona:
    def __init__(self):
        self.calls = []
        self.status = {}
        self.reference = {}
        self.count = 0

    def call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "POST" and path == "/inquiries":
            self.count += 1
            inquiry = f"inq_{self.count}"
            self.status[inquiry] = "created"
            self.reference[inquiry] = body["data"]["attributes"]["reference-id"]
            return {"data": {"id": inquiry, "attributes": {"status": "created"}}, "meta": {}}
        if method == "POST" and path.endswith("/resume"):
            return {"data": {"id": path.split("/")[2]}, "meta": {"session-token": "sess_resume"}}
        if method == "GET":
            inquiry = path.split("/")[2]
            return {"data": {"id": inquiry, "attributes": {"status": self.status[inquiry], "reference-id": self.reference[inquiry]}}}
        raise AssertionError(path)


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(User(id="ada", email="ada@example.com", password_hash="x", first_name="Ada", last_name="Mensah", status="active"))
        db.add(User(id="kofi", email="kofi@example.com", password_hash="x", first_name="Kofi", last_name="Boateng", status="active"))
        db.commit()

    settings = identity.get_settings()
    monkeypatch.setattr(settings, "persona_api_key", "persona_sandbox_test")
    monkeypatch.setattr(settings, "persona_template_id", "itmpl_test")
    monkeypatch.setattr(settings, "persona_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "app_url", "http://localhost:3000")
    persona = FakePersona()
    monkeypatch.setattr(identity, "persona_call", persona.call)
    sent = []
    monkeypatch.setattr(email_service, "deliver", lambda to, subject, *rest: sent.append((to, subject)) or True)
    monkeypatch.setattr(email_service, "_pool", type("Now", (), {"submit": staticmethod(lambda fn, *a: fn(*a))})())

    app = FastAPI()
    app.include_router(identity.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    who = {"id": "ada"}
    app.dependency_overrides[get_current_user_id] = lambda: who["id"]
    return TestClient(app), Session, persona, who, sent


def signed(event: dict, stamp=None, extra_signature=None):
    raw = json.dumps(event)
    stamp = stamp or int(time.time())
    digest = hmac.new(SECRET.encode(), f"{stamp}.{raw}".encode(), hashlib.sha256).hexdigest()
    header = f"t={stamp},v1={digest}" if not extra_signature else f"t={stamp},v1={extra_signature} v1={digest}"
    return raw, header


def inquiry_event(inquiry_id, claimed_status="approved"):
    return {"data": {"attributes": {"name": "inquiry.approved", "payload": {"data": {
        "type": "inquiry", "id": inquiry_id, "attributes": {"status": claimed_status}}}}}}


def test_start_creates_an_inquiry_for_this_user_and_sends_them_to_persona(env):
    client, _, persona, _, _ = env
    assert client.get("/api/v1/identity/status").json()["state"] == "not_started"
    url = client.post("/api/v1/identity/start").json()["url"]
    query = parse_qs(urlparse(url).query)
    assert query["inquiry-id"] == ["inq_1"] and query["redirect-uri"] == ["http://localhost:3000/face-verification?done=1"]
    attributes = persona.calls[0][2]["data"]["attributes"]
    assert attributes["reference-id"] == "ada" and attributes["inquiry-template-id"] == "itmpl_test"
    assert attributes["fields"]["email-address"] == "ada@example.com"
    # Coming back to it resumes the same inquiry instead of starting over
    again = parse_qs(urlparse(client.post("/api/v1/identity/start").json()["url"]).query)
    assert again["inquiry-id"] == ["inq_1"] and again["session-token"] == ["sess_resume"]
    assert client.get("/api/v1/identity/status").json()["state"] == "in_progress"


def test_the_result_comes_from_persona_and_is_announced_once(env):
    client, Session, persona, _, sent = env
    client.post("/api/v1/identity/start")
    persona.status["inq_1"] = "completed"
    assert client.post("/api/v1/identity/refresh").json()["state"] == "verified"
    client.post("/api/v1/identity/refresh")
    with Session() as db:
        assert db.get(User, "ada").is_verified is True
        assert db.query(Notification).filter(Notification.title == "Identity verified").count() == 1
    assert sent == [("ada@example.com", "Identity verified · Hoardrun")]
    assert client.post("/api/v1/identity/start").status_code == 409


def test_a_declined_check_can_be_tried_again(env):
    client, _, persona, _, _ = env
    client.post("/api/v1/identity/start")
    persona.status["inq_1"] = "declined"
    body = client.post("/api/v1/identity/refresh").json()
    assert body["state"] == "declined" and body["can_start"] is True
    url = client.post("/api/v1/identity/start").json()["url"]
    assert parse_qs(urlparse(url).query)["inquiry-id"] == ["inq_2"]


def test_a_check_under_review_waits(env):
    client, _, persona, _, _ = env
    client.post("/api/v1/identity/start")
    persona.status["inq_1"] = "needs_review"
    assert client.post("/api/v1/identity/refresh").json()["state"] == "in_review"
    assert client.post("/api/v1/identity/start").status_code == 409


def test_an_inquiry_for_someone_else_never_verifies_this_user(env):
    client, Session, persona, _, _ = env
    client.post("/api/v1/identity/start")
    persona.reference["inq_1"], persona.status["inq_1"] = "kofi", "approved"
    assert client.post("/api/v1/identity/refresh").json()["state"] == "in_progress"
    with Session() as db:
        assert not db.get(User, "ada").is_verified


def test_webhooks_need_a_fresh_valid_signature_and_their_body_is_not_trusted(env):
    client, Session, persona, _, _ = env
    client.post("/api/v1/identity/start")
    event = inquiry_event("inq_1", claimed_status="approved")
    raw, header = signed(event)
    assert client.post("/api/v1/identity/webhook", content=raw).status_code == 400
    assert client.post("/api/v1/identity/webhook", content=raw, headers={"persona-signature": "t=1,v1=bad"}).status_code == 400
    stale_raw, stale_header = signed(event, stamp=int(time.time()) - 3600)
    assert client.post("/api/v1/identity/webhook", content=stale_raw, headers={"persona-signature": stale_header}).status_code == 400

    # Signed, but the body's "approved" isn't taken at its word: Persona says it's still pending
    persona.status["inq_1"] = "pending"
    assert client.post("/api/v1/identity/webhook", content=raw, headers={"persona-signature": header}).status_code == 200
    assert client.get("/api/v1/identity/status").json()["state"] == "in_progress"

    # During a secret rotation Persona sends two signatures; either may match
    persona.status["inq_1"] = "approved"
    raw2, header2 = signed(event, extra_signature="0" * 64)
    assert client.post("/api/v1/identity/webhook", content=raw2, headers={"persona-signature": header2}).status_code == 200
    assert client.get("/api/v1/identity/status").json()["state"] == "verified"


def test_moving_money_out_needs_a_verified_identity_once_checks_are_on(env, monkeypatch):
    client, Session, persona, _, _ = env
    with Session() as db:
        with pytest.raises(HTTPException) as refused:
            identity.require_verified_identity(db, "ada", "send money")
        assert refused.value.status_code == 403 and "Verify your identity to send money" in refused.value.detail
    client.post("/api/v1/identity/start")
    persona.status["inq_1"] = "approved"
    client.post("/api/v1/identity/refresh")
    with Session() as db:
        identity.require_verified_identity(db, "ada", "send money")

    # Without Persona set up, development lets money move; production never does
    monkeypatch.setattr(identity.get_settings(), "persona_api_key", "")
    with Session() as db:
        identity.require_verified_identity(db, "kofi", "send money")
        monkeypatch.setenv("ENVIRONMENT", "production")
        with pytest.raises(HTTPException):
            identity.require_verified_identity(db, "kofi", "send money")


def test_not_configured_says_so(env, monkeypatch):
    client, _, _, _, _ = env
    monkeypatch.setattr(identity.get_settings(), "persona_template_id", "")
    assert client.get("/api/v1/identity/status").json()["configured"] is False
    response = client.post("/api/v1/identity/start")
    assert response.status_code == 503 and response.json()["detail"] == "Identity checks aren't set up yet"
