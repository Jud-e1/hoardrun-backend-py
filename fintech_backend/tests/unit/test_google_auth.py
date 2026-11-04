"""
Sign in with Google. Google's token endpoint is faked; everything else is real.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_google_auth.py --noconftest --import-mode=importlib
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

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import google_auth
from app.auth.jwt_handler import JWTHandler
from app.database.config import Base, get_db
from app.database.models import User
from app.services import email_service
from app.services.inbox import Notification

CLIENT_ID = "hoardrun-test.apps.googleusercontent.com"


def unsigned_jwt(claims: dict) -> str:
    part = lambda obj: base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()  # noqa: E731
    return f"{part({'alg': 'RS256'})}.{part(claims)}.signature"


class FakeGoogle:
    def __init__(self):
        self.claims = {}
        self.verifiers = []

    def exchange(self, code, verifier):
        self.verifiers.append(verifier)
        return {"access_token": "ya29.x", "id_token": unsigned_jwt(self.claims)}


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
        db.add(User(id="kofi", email="kofi@example.com", password_hash="x", first_name="Kofi", last_name="Boateng",
                    status="pending", email_verified=False))
        db.commit()

    settings = google_auth.get_settings()
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "google_client_secret", "GOCSPX-test")
    monkeypatch.setattr(settings, "app_url", "http://localhost:3000")
    google = FakeGoogle()
    monkeypatch.setattr(google_auth, "exchange_code", google.exchange)
    sent = []
    monkeypatch.setattr(email_service, "deliver", lambda to, subject, *rest: sent.append((to, subject)) or True)
    monkeypatch.setattr(email_service, "_pool", type("Now", (), {"submit": staticmethod(lambda fn, *a: fn(*a))})())

    app = FastAPI()
    app.include_router(google_auth.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    return TestClient(app), Session, google, sent


def start(client, **body):
    response = client.post("/api/v1/auth/google/start", json=body or {"mode": "signin"})
    assert response.status_code == 200, response.text
    query = parse_qs(urlparse(response.json()["url"]).query)
    return {key: values[0] for key, values in query.items()}


def claims(nonce, **extra):
    base = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "exp": int(time.time()) + 600, "nonce": nonce,
            "sub": "google-123", "email": "nana@gmail.com", "email_verified": True, "given_name": "Nana", "family_name": "Owusu"}
    base.update(extra)
    return base


def finish(client, google, params, **extra):
    google.claims = claims(extra.pop("nonce", params["nonce"]), **extra)
    return client.post("/api/v1/auth/google/callback", json={"code": "4/0AX-test-code", "state": params["state"]})


def test_start_asks_google_for_a_code_with_pkce_and_a_nonce(env):
    client, Session, google, _ = env
    params = start(client, mode="signup", next="/savings")
    assert params["client_id"] == CLIENT_ID and params["redirect_uri"] == "http://localhost:3000/auth/google/callback"
    assert params["code_challenge_method"] == "S256" and params["scope"] == "openid email profile"
    with Session() as db:
        stored = db.query(google_auth.OAuthState).one()
        assert stored.state_hash != params["state"] and stored.next_path == "/savings"
        challenge = base64.urlsafe_b64encode(hashlib.sha256(stored.verifier.encode()).digest()).rstrip(b"=").decode()
        assert challenge == params["code_challenge"]


def test_a_new_google_user_gets_an_active_verified_account_and_a_session(env):
    client, Session, google, _ = env
    params = start(client, next="/savings")
    response = finish(client, google, params)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["new_user"] is True and data["next"] == "/savings"
    assert data["user"]["email"] == "nana@gmail.com" and data["user"]["email_verified"] is True
    user_id = JWTHandler.get_user_id_from_token(data["access_token"])
    with Session() as db:
        user = db.get(User, user_id)
        assert user.status == "active" and user.first_name == "Nana"
        # The PKCE verifier Google got is the one kept for this sign-in
        assert len(google.verifiers) == 1


def test_signing_in_again_finds_the_same_account(env):
    client, Session, google, _ = env
    first = finish(client, google, start(client)).json()["data"]
    again = finish(client, google, start(client)).json()["data"]
    assert again["new_user"] is False and again["user"]["id"] == first["user"]["id"]
    with Session() as db:
        assert db.query(google_auth.UserIdentity).count() == 1


def test_an_existing_account_with_that_email_is_linked_and_its_owner_told(env):
    client, Session, google, sent = env
    data = finish(client, google, start(client), email="ada@example.com", sub="google-ada").json()["data"]
    assert data["user"]["id"] == "ada" and data["new_user"] is False
    with Session() as db:
        assert db.query(Notification).filter(Notification.user_id == "ada", Notification.title == "Google sign-in added").count() == 1
    assert ("ada@example.com", "Google sign-in added · Hoardrun") in sent


def test_google_confirms_an_unverified_email(env):
    client, Session, google, _ = env
    assert finish(client, google, start(client), email="kofi@example.com", sub="google-kofi").status_code == 200
    with Session() as db:
        kofi = db.get(User, "kofi")
        assert kofi.status == "active" and kofi.email_verified


def test_a_state_works_once_and_not_after_ten_minutes(env):
    client, Session, google, _ = env
    params = start(client)
    assert finish(client, google, params).status_code == 200
    assert finish(client, google, params).status_code == 400
    late = start(client)
    with Session() as db:
        db.query(google_auth.OAuthState).update({google_auth.OAuthState.expires_at: datetime.utcnow() - timedelta(seconds=1)})
        db.commit()
    assert finish(client, google, late).status_code == 400
    made_up = client.post("/api/v1/auth/google/callback", json={"code": "4/0AX-test-code", "state": "x" * 43})
    assert made_up.status_code == 400


@pytest.mark.parametrize("bad", [
    {"nonce": "someone-elses-nonce"},
    {"aud": "another-app.apps.googleusercontent.com"},
    {"iss": "https://evil.example"},
    {"email_verified": False},
    {"exp": int(time.time()) - 3600},
])
def test_id_tokens_that_dont_check_out_are_refused(env, bad):
    client, Session, google, _ = env
    response = finish(client, google, start(client), **bad)
    assert response.status_code == 400
    with Session() as db:
        assert db.query(User).filter(User.email == "nana@gmail.com").count() == 0


def test_a_closed_account_stays_closed(env):
    client, _, google, _ = env
    response = finish(client, google, start(client), email="gone@example.com", sub="google-gone")
    assert response.status_code == 403 and response.json()["detail"] == "This account is closed."


def test_only_app_paths_are_kept_for_after_sign_in(env):
    assert google_auth.safe_next("/savings") == "/savings"
    for bad in ("//evil.example", "https://evil.example", "/\\evil.example", None, ""):
        assert google_auth.safe_next(bad) is None


def test_not_configured_says_so(env, monkeypatch):
    client, _, _, _ = env
    monkeypatch.setattr(google_auth.get_settings(), "google_client_secret", "")
    assert client.get("/api/v1/auth/google/status").json() == {"configured": False}
    response = client.post("/api/v1/auth/google/start", json={"mode": "signin"})
    assert response.status_code == 503 and response.json()["detail"] == "Google sign-in isn't set up yet"


def test_password_sign_in_still_issues_the_same_kind_of_session(env):
    import asyncio
    from app.auth import passwords
    from app.core.exceptions import AuthenticationException
    from app.models.auth import UserLoginRequest
    from app.services.auth_service import AuthService
    _, Session, _, _ = env
    with Session() as db:
        db.get(User, "ada").password_hash = passwords.hash_password("Right-Passw0rd")
        db.commit()
        login = asyncio.run(AuthService().authenticate_user(UserLoginRequest(email="ada@example.com", password="Right-Passw0rd"), db))
        assert JWTHandler.get_user_id_from_token(login.access_token) == "ada" and login.user.email == "ada@example.com"
        with pytest.raises(AuthenticationException):
            asyncio.run(AuthService().authenticate_user(UserLoginRequest(email="ada@example.com", password="Wrong-Passw0rd"), db))


def test_sign_in_from_the_phone_app_needs_the_apps_secret(env):
    client, Session, google, _ = env
    secret = "app-secret-" + "x" * 40
    proof_hash = hashlib.sha256(secret.encode()).hexdigest()

    # Someone who caught the hoardrun:// link has the code and state, but not the secret
    caught = start(client, mode="signin", app_proof_hash=proof_hash)
    assert caught["state"].startswith("a_")
    assert finish(client, google, caught).status_code == 400
    google.claims = claims(caught["nonce"])
    again = client.post("/api/v1/auth/google/callback",
                        json={"code": "4/0AX-test-code", "state": caught["state"], "app_proof": secret})
    assert again.status_code == 400  # the state was used up by the failed try

    params = start(client, mode="signin", app_proof_hash=proof_hash)
    google.claims = claims(params["nonce"])
    wrong = client.post("/api/v1/auth/google/callback",
                        json={"code": "4/0AX-test-code", "state": params["state"], "app_proof": "y" * 40})
    assert wrong.status_code == 400

    params = start(client, mode="signin", app_proof_hash=proof_hash)
    google.claims = claims(params["nonce"])
    ok = client.post("/api/v1/auth/google/callback",
                     json={"code": "4/0AX-test-code", "state": params["state"], "app_proof": secret})
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["access_token"]


def test_the_website_sign_in_is_unchanged(env):
    client, _, google, _ = env
    params = start(client)
    assert not params["state"].startswith("a_")
    assert finish(client, google, params).status_code == 200
