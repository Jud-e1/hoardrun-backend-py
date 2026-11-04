"""
Sign in with Apple. Apple's token endpoint is faked; the client secret is signed with a real test key.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_apple_auth.py --noconftest --import-mode=importlib
"""

import base64
import hashlib
import json
import os
import time
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import apple_auth, google_auth
from app.database.config import Base, get_db
from app.database.models import User
from app.services import email_service
from app.services.inbox import Notification

SERVICES_ID = "com.hoardrun.signin"
KEY = ec.generate_private_key(ec.SECP256R1())
KEY_PEM = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()


def unsigned_jwt(claims: dict) -> str:
    part = lambda obj: base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()  # noqa: E731
    return f"{part({'alg': 'RS256'})}.{part(claims)}.signature"


class FakeApple:
    def __init__(self):
        self.claims = {}
        self.secrets = []

    def exchange(self, code):
        # The real client secret is built for every exchange
        self.secrets.append(apple_auth.client_secret())
        return {"access_token": "a.x", "id_token": unsigned_jwt(self.claims)}


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(User(id="ada", email="ada@example.com", password_hash="x", first_name="Ada", last_name="Mensah",
                    status="active", email_verified=True))
        db.add(User(id="gone", email="gone@example.com", password_hash="x", first_name="Gone", last_name="User",
                    status="deactivated", email_verified=True))
        db.commit()

    settings = apple_auth.get_settings()
    for name, value in {"apple_services_id": SERVICES_ID, "apple_team_id": "TEAM123456", "apple_key_id": "KEY1234567",
                        "apple_private_key": KEY_PEM.replace("\n", "\\n"), "app_url": "http://localhost:3000",
                        "api_url": "http://localhost:8000", "google_client_id": "g", "google_client_secret": "g"}.items():
        monkeypatch.setattr(settings, name, value)
    apple = FakeApple()
    monkeypatch.setattr(apple_auth, "exchange_code", apple.exchange)
    monkeypatch.setattr(email_service, "deliver", lambda *a: True)
    monkeypatch.setattr(email_service, "_pool", type("Now", (), {"submit": staticmethod(lambda fn, *a: fn(*a))})())

    app = FastAPI()
    app.include_router(apple_auth.router, prefix="/api/v1")
    app.include_router(google_auth.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    return TestClient(app), Session, apple


def start(client, **body):
    response = client.post("/api/v1/auth/apple/start", json=body or {"mode": "signin"})
    assert response.status_code == 200, response.text
    query = parse_qs(urlparse(response.json()["url"]).query)
    return {key: values[0] for key, values in query.items()}


def claims(nonce, **extra):
    base = {"iss": "https://appleid.apple.com", "aud": SERVICES_ID, "exp": int(time.time()) + 600, "nonce": nonce,
            "sub": "001234.apple", "email": "nana@privaterelay.appleid.com", "email_verified": "true"}
    base.update(extra)
    return base


def post_back(client, apple, params, user=None, **extra):
    """Apple posting the sign-in back as a form; returns where we send the person."""
    apple.claims = claims(extra.pop("nonce", params["nonce"]), **extra)
    form = {"code": "c" + "x" * 30, "state": params["state"]}
    if user:
        form["user"] = json.dumps(user)
    response = client.post("/api/v1/auth/apple/callback", data=form, follow_redirects=False)
    assert response.status_code == 303
    location = urlparse(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == "http://localhost:3000/auth/apple/callback"
    return {key: values[0] for key, values in parse_qs(location.query).items()}


def redeem(client, ticket, **extra):
    return client.post("/api/v1/auth/apple/redeem", json={"ticket": ticket, **extra})


def test_start_asks_apple_to_post_the_name_and_email_back_to_the_api(env):
    client, _, _ = env
    params = start(client, next="/savings")
    assert params["client_id"] == SERVICES_ID and params["response_mode"] == "form_post"
    assert params["redirect_uri"] == "http://localhost:8000/api/v1/auth/apple/callback"
    assert params["scope"] == "name email" and params["nonce"] and not params["state"].startswith("a_")


def test_a_new_apple_user_gets_an_account_with_the_name_apple_sends_once(env):
    client, Session, apple = env
    back = post_back(client, apple, start(client, next="/savings"),
                     user={"name": {"firstName": "Nana", "lastName": "Owusu"}})
    data = redeem(client, back["ticket"]).json()["data"]
    assert data["access_token"] and data["new_user"] is True and data["next"] == "/savings"
    with Session() as db:
        user = db.query(User).filter(User.email == "nana@privaterelay.appleid.com").one()
        assert (user.first_name, user.last_name, user.status, user.email_verified) == ("Nana", "Owusu", "active", True)

    # The client secret is a short-lived ES256 token Apple can check with the public key
    secret = apple.secrets[-1]
    header = jwt.get_unverified_header(secret)
    body = jwt.decode(secret, KEY.public_key(), algorithms=["ES256"], audience="https://appleid.apple.com")
    assert header["kid"] == "KEY1234567" and body["iss"] == "TEAM123456" and body["sub"] == SERVICES_ID
    assert body["exp"] - body["iat"] <= 300

    # Signing in again (Apple sends no name now) finds the same account
    again = post_back(client, apple, start(client))
    assert redeem(client, again["ticket"]).json()["data"]["new_user"] is False


def test_an_existing_account_with_that_email_is_linked_and_its_owner_told(env):
    client, Session, apple = env
    back = post_back(client, apple, start(client), email="ada@example.com", sub="apple-ada")
    assert redeem(client, back["ticket"]).json()["data"]["user"]["id"] == "ada"
    with Session() as db:
        assert db.query(Notification).filter(Notification.user_id == "ada",
                                             Notification.title == "Sign in with Apple added").count() == 1


def test_a_ticket_works_once_and_not_after_two_minutes(env):
    client, Session, apple = env
    ticket = post_back(client, apple, start(client))["ticket"]
    assert redeem(client, ticket).status_code == 200
    assert redeem(client, ticket).status_code == 400

    late = post_back(client, apple, start(client))["ticket"]
    with Session() as db:
        db.query(apple_auth.AuthTicket).update({"expires_at": datetime.utcnow() - timedelta(seconds=1)})
        db.commit()
    assert redeem(client, late).status_code == 400
    assert redeem(client, "made-up-ticket-" + "x" * 30).status_code == 400


@pytest.mark.parametrize("bad", [
    {"aud": "someone-else"}, {"iss": "https://evil.example"}, {"exp": 1}, {"nonce": "other"},
    {"email_verified": "false"},
])
def test_id_tokens_that_dont_check_out_send_the_person_back_with_an_error(env, bad):
    client, _, apple = env
    back = post_back(client, apple, start(client), **bad)
    assert back == {"error": "failed"}


def test_a_state_works_once_and_a_google_state_cant_finish_here(env):
    client, _, apple = env
    params = start(client)
    assert "ticket" in post_back(client, apple, params)
    assert post_back(client, apple, params) == {"error": "expired"}

    google_state = client.post("/api/v1/auth/google/start", json={"mode": "signin"}).json()["url"]
    google_params = {k: v[0] for k, v in parse_qs(urlparse(google_state).query).items()}
    assert post_back(client, apple, google_params) == {"error": "expired"}


def test_an_apple_state_cant_finish_at_googles_callback(env):
    client, _, _ = env
    params = start(client)
    response = client.post("/api/v1/auth/google/callback", json={"code": "4/0AX-test-code", "state": params["state"]})
    assert response.status_code == 400


def test_cancelling_at_apple_and_closed_accounts(env):
    client, _, apple = env
    params = start(client)
    response = client.post("/api/v1/auth/apple/callback", follow_redirects=False,
                           data={"state": params["state"], "error": "user_cancelled_authorize"})
    assert "error=cancelled" in response.headers["location"]
    assert post_back(client, apple, start(client), email="gone@example.com", sub="apple-gone") == {"error": "closed"}


def test_sign_in_from_the_phone_app_needs_the_apps_secret(env):
    client, _, apple = env
    secret = "app-secret-" + "x" * 40
    proof_hash = hashlib.sha256(secret.encode()).hexdigest()

    params = start(client, app_proof_hash=proof_hash)
    assert params["state"].startswith("a_")
    ticket = post_back(client, apple, params)["ticket"]
    # The page uses the a_ prefix to hand the ticket back to the app
    assert ticket.startswith("a_")
    # Someone who caught the hoardrun:// link has the ticket but not the secret; the ticket is then used up
    assert redeem(client, ticket).status_code == 400
    assert redeem(client, ticket, app_proof=secret).status_code == 400

    ticket = post_back(client, apple, start(client, app_proof_hash=proof_hash))["ticket"]
    assert redeem(client, ticket, app_proof="y" * 40).status_code == 400
    ticket = post_back(client, apple, start(client, app_proof_hash=proof_hash))["ticket"]
    assert redeem(client, ticket, app_proof=secret).status_code == 200

    # Errors for an app sign-in say so, so the page can hand them to the app too
    params = start(client, app_proof_hash=proof_hash)
    response = client.post("/api/v1/auth/apple/callback", follow_redirects=False,
                           data={"state": params["state"], "error": "user_cancelled_authorize"})
    assert "app=1" in response.headers["location"]


def test_not_configured_says_so(env, monkeypatch):
    client, _, _ = env
    monkeypatch.setattr(apple_auth.get_settings(), "apple_private_key", "")
    assert client.get("/api/v1/auth/apple/status").json() == {"configured": False}
    assert client.post("/api/v1/auth/apple/start", json={"mode": "signin"}).status_code == 503
