"""
Sign in with Google (OpenID Connect, authorization code flow).

1. /start makes a one-time state, a nonce and a PKCE pair, and returns Google's consent URL.
2. Google sends the person to APP_URL/auth/google/callback; that page posts the code and state here.
3. /callback checks the state (once, within 10 minutes), swaps the code with Google using the
   client secret and PKCE verifier, and checks the ID token: issuer, audience, expiry, nonce,
   and that Google verified the email.

In the iPhone and Android apps Google refuses to sign in inside the app, so the app opens Google in
the phone's browser. The app keeps a random secret and sends only its hash to /start; the state then
starts with "a_", and the callback page hands the code back to the app through a hoardrun:// link.
/callback for such a state needs the secret itself, so a code caught on its way to the app is useless.

The ID token comes straight from Google's token endpoint over TLS, so OpenID Connect allows
trusting it without checking its signature. Accounts are matched by Google's account ID; an
existing Hoardrun account with the same verified email is linked, and its owner is emailed.
"""

import base64
import hashlib
import json
import logging
import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Literal, Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Session

from ...auth import passwords
from ...config.settings import get_settings
from ...database.config import Base, get_db
from ...database.models import User
from ...services.auth_service import AuthService
from ...services.inbox import notify
from ...utils.response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/google", tags=["Authentication"])

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
STATE_LIFETIME = timedelta(minutes=10)


class OAuthState(Base):
    """A sign-in that has been started but not finished."""
    __tablename__ = "oauth_states"

    state_hash = Column(String(64), primary_key=True)
    verifier = Column(String(128), nullable=False)
    nonce = Column(String(64), nullable=False)
    mode = Column(String(10), nullable=False)
    next_path = Column(String(200))
    # Set when the sign-in was started from the phone app: the hash of a secret only the app holds
    app_proof_hash = Column(String(64))
    expires_at = Column(DateTime, nullable=False)


class UserIdentity(Base):
    """A sign-in method from outside Hoardrun linked to an account (today, Google)."""
    __tablename__ = "user_identities"
    __table_args__ = (UniqueConstraint("provider", "subject", name="uq_identity_subject"),)

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(20), nullable=False)
    subject = Column(String(255), nullable=False)
    email = Column(String(320))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class StartRequest(BaseModel):
    mode: Literal["signin", "signup"] = "signin"
    next: Optional[str] = Field(None, max_length=200)
    # From the phone app only: SHA-256 (hex) of a random secret the app keeps until the callback
    app_proof_hash: Optional[str] = Field(None, pattern=r"^[0-9a-f]{64}$")


class CallbackRequest(BaseModel):
    code: str = Field(min_length=10, max_length=2000)
    state: str = Field(min_length=20, max_length=200)
    app_proof: Optional[str] = Field(None, min_length=32, max_length=200)


APP_STATE_PREFIX = "a_"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def configured() -> bool:
    settings = get_settings()
    return bool(settings.google_client_id and settings.google_client_secret)


def redirect_uri() -> str:
    return get_settings().app_url.rstrip("/") + "/auth/google/callback"


def safe_next(path: Optional[str]) -> Optional[str]:
    """Only app paths, so the sign-in can't be used to send someone to another site."""
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path:
        return None
    return path


def exchange_code(code: str, verifier: str) -> dict:
    """Google's token response for an authorization code. Tests replace this."""
    settings = get_settings()
    response = httpx.post(TOKEN_URL, timeout=15, data={
        "code": code, "client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
        "redirect_uri": redirect_uri(), "grant_type": "authorization_code", "code_verifier": verifier,
    })
    if response.status_code != 200:
        logger.warning("Google token exchange failed: %s %s", response.status_code, response.text[:200])
        raise HTTPException(status_code=400, detail="Google didn't accept that sign-in. Try again.")
    return response.json()


def id_token_claims(id_token: str) -> dict:
    try:
        payload = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError):
        raise HTTPException(status_code=400, detail="Google sent something we couldn't read. Try again.")


def check_claims(claims: dict, nonce: str) -> None:
    settings = get_settings()
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if claims.get("iss") not in ISSUERS or settings.google_client_id not in audiences:
        raise HTTPException(status_code=400, detail="That sign-in wasn't meant for Hoardrun.")
    if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] < time.time() - 60:
        raise HTTPException(status_code=400, detail="That Google sign-in expired. Try again.")
    if not secrets.compare_digest(str(claims.get("nonce") or ""), nonce):
        raise HTTPException(status_code=400, detail="That Google sign-in didn't match. Try again.")
    if not claims.get("sub") or not claims.get("email") or claims.get("email_verified") not in (True, "true"):
        raise HTTPException(status_code=400, detail="Your Google account needs a verified email to sign in.")


def find_or_create_user(db: Session, claims: dict, provider: str = "google") -> tuple[User, str]:
    """The account for this Google (or Apple) identity, and how it was found: existing, linked or created."""
    subject, email = str(claims["sub"]), str(claims["email"]).strip().lower()
    identity = db.query(UserIdentity).filter(UserIdentity.provider == provider, UserIdentity.subject == subject).first()
    if identity is not None:
        user = db.get(User, identity.user_id)
        if user is not None:
            return user, "existing"
        db.delete(identity)
        db.flush()

    user = db.query(User).filter(User.email == email).first() or db.query(User).filter(User.email == claims["email"]).first()
    how = "linked"
    if user is None:
        how = "created"
        user = User(
            email=email, first_name=(claims.get("given_name") or email.split("@")[0])[:50],
            last_name=(claims.get("family_name") or "")[:50] or "-",
            # No password until the person sets one with Forgot password
            password_hash=passwords.hash_password(secrets.token_urlsafe(32)),
            status="active", role="user", email_verified=True, profile_picture_url=claims.get("picture"),
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        db.add(user)
        db.flush()
    db.add(UserIdentity(id=str(uuid.uuid4()), user_id=user.id, provider=provider, subject=subject, email=email))
    return user, how


@router.get("/status")
async def google_status():
    return {"configured": configured()}


@router.post("/start")
async def start(payload: StartRequest, db: Session = Depends(get_db)):
    if not configured():
        raise HTTPException(status_code=503, detail="Google sign-in isn't set up yet")
    state, verifier, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(64), secrets.token_urlsafe(24)
    if payload.app_proof_hash:
        # Tells the callback page to hand the code back to the app
        state = APP_STATE_PREFIX + state
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    now = datetime.utcnow()
    db.query(OAuthState).filter(OAuthState.expires_at < now).delete(synchronize_session=False)
    db.add(OAuthState(state_hash=_hash(state), verifier=verifier, nonce=nonce, mode=payload.mode,
                      next_path=safe_next(payload.next), app_proof_hash=payload.app_proof_hash,
                      expires_at=now + STATE_LIFETIME))
    db.commit()
    url = AUTHORIZE_URL + "?" + urlencode({
        "client_id": get_settings().google_client_id, "redirect_uri": redirect_uri(), "response_type": "code",
        "scope": "openid email profile", "state": state, "nonce": nonce, "code_challenge": challenge,
        "code_challenge_method": "S256", "prompt": "select_account",
    })
    return {"url": url}


@router.post("/callback")
async def callback(payload: CallbackRequest, db: Session = Depends(get_db)):
    if not configured():
        raise HTTPException(status_code=503, detail="Google sign-in isn't set up yet")
    pending = db.get(OAuthState, _hash(payload.state))
    # Apple sign-ins share this table; they can only finish at Apple's callback
    if pending is None or pending.mode == "apple" or pending.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="That sign-in took too long or was already used. Try again.")
    verifier, nonce, next_path = pending.verifier, pending.nonce, pending.next_path
    proof_ok = pending.app_proof_hash is None or (
        payload.app_proof is not None and secrets.compare_digest(_hash(payload.app_proof), pending.app_proof_hash))
    # Used once, whatever happens next
    db.delete(pending)
    db.commit()
    if not proof_ok:
        # Started in the app but finished somewhere else: someone may have caught the link
        raise HTTPException(status_code=400, detail="Finish signing in with Google in the Hoardrun app. Try again.")

    tokens = exchange_code(payload.code, verifier)
    claims = id_token_claims(str(tokens.get("id_token") or ""))
    check_claims(claims, nonce)

    user, how = find_or_create_user(db, claims)
    if user.status == "deactivated":
        db.rollback()
        raise HTTPException(status_code=403, detail="This account is closed.")
    if user.status != "active" or not user.email_verified:
        # Google has just confirmed this email belongs to them
        user.status, user.email_verified = "active", True
    if how == "linked":
        notify(db, user.id, "security", "Google sign-in added",
               f"You can now sign in to Hoardrun with Google ({claims['email']}). If this wasn't you, contact support right away.",
               link="/security", key=f"google-linked:{claims['sub']}")
    db.commit()

    service = AuthService()
    login = await service.login_data_for(await service._get_user_by_id(user.id, db), db)
    data = jsonable_encoder(login)
    data.update({"new_user": how == "created", "next": next_path})
    return success_response(data=data, message="Signed in with Google")
