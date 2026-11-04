"""
Sign in with Apple (web flow, used by the website and the phone apps).

Apple requires it in the App Store for any app that offers Google sign-in (App Review 4.8).

1. /start makes a one-time state and nonce (stored with mode "apple" in oauth_states) and returns
   Apple's consent URL. From the phone app, the hash of the app's secret is stored too and the state
   starts with "a_", as for Google.
2. Apple posts the code back to API_URL/api/v1/auth/apple/callback (Apple only posts, and only to a
   server, when asking for the name and email). We swap the code with Apple using a client secret
   signed with the Sign in with Apple key, check the ID token, find or create the account, and send
   the person to APP_URL/auth/apple/callback with a one-time ticket that lasts 2 minutes.
3. That page redeems the ticket at /redeem for a Hoardrun session. A ticket from the app needs the
   app's secret, so one caught on its way back to the app is useless.

The ID token comes straight from Apple's token endpoint over TLS, so OpenID Connect allows trusting
it without checking its signature. Apple sends the person's name only the first time they sign in.
"""

import hashlib
import json
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Literal, Optional
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.orm import Session

from ...config.settings import get_settings
from ...database.config import Base, get_db
from ...services.auth_service import AuthService
from ...services.inbox import notify
from ...utils.response import success_response
from .google_auth import APP_STATE_PREFIX, OAuthState, find_or_create_user, id_token_claims, safe_next

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/apple", tags=["Authentication"])

AUTHORIZE_URL = "https://appleid.apple.com/auth/authorize"
TOKEN_URL = "https://appleid.apple.com/auth/token"
ISSUER = "https://appleid.apple.com"
STATE_LIFETIME = timedelta(minutes=10)
TICKET_LIFETIME = timedelta(minutes=2)


class AuthTicket(Base):
    """A finished Apple sign-in waiting to be turned into a Hoardrun session, once, within 2 minutes."""
    __tablename__ = "auth_tickets"

    ticket_hash = Column(String(64), primary_key=True)
    user_id = Column(String, nullable=False)
    new_user = Column(Boolean, nullable=False, default=False)
    next_path = Column(String(200))
    app_proof_hash = Column(String(64))
    expires_at = Column(DateTime, nullable=False)


class StartRequest(BaseModel):
    mode: Literal["signin", "signup"] = "signin"
    next: Optional[str] = Field(None, max_length=200)
    app_proof_hash: Optional[str] = Field(None, pattern=r"^[0-9a-f]{64}$")


class RedeemRequest(BaseModel):
    ticket: str = Field(min_length=20, max_length=200)
    app_proof: Optional[str] = Field(None, min_length=32, max_length=200)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def configured() -> bool:
    s = get_settings()
    return bool(s.apple_services_id and s.apple_team_id and s.apple_key_id and s.apple_private_key)


def redirect_uri() -> str:
    return get_settings().api_url.rstrip("/") + "/api/v1/auth/apple/callback"


def client_secret() -> str:
    """Apple's 'client secret' is a short-lived JWT signed with the Sign in with Apple key (ES256)."""
    s = get_settings()
    now = int(time.time())
    key = s.apple_private_key.replace("\\n", "\n")
    return jwt.encode(
        {"iss": s.apple_team_id, "iat": now, "exp": now + 300, "aud": ISSUER, "sub": s.apple_services_id},
        key, algorithm="ES256", headers={"kid": s.apple_key_id},
    )


def exchange_code(code: str) -> dict:
    """Apple's token response for an authorization code. Tests replace this."""
    response = httpx.post(TOKEN_URL, timeout=15, data={
        "client_id": get_settings().apple_services_id, "client_secret": client_secret(), "code": code,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri(),
    })
    if response.status_code != 200:
        logger.warning("Apple token exchange failed with status %s", response.status_code)
        raise ValueError("Apple didn't accept that sign-in")
    return response.json()


def check_claims(claims: dict, nonce: str) -> None:
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if claims.get("iss") != ISSUER or get_settings().apple_services_id not in audiences:
        raise ValueError("That sign-in wasn't meant for Hoardrun")
    if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] < time.time() - 60:
        raise ValueError("That Apple sign-in expired")
    if not secrets.compare_digest(str(claims.get("nonce") or ""), nonce):
        raise ValueError("That Apple sign-in didn't match")
    if not claims.get("sub") or not claims.get("email") or claims.get("email_verified") not in (True, "true"):
        raise ValueError("Your Apple ID needs a verified email to sign in")


def back_to_app_url(*, ticket: Optional[str] = None, error: Optional[str] = None, from_app: bool = False) -> str:
    """The web page that finishes the sign-in (and hands it to the phone app when it started there)."""
    params = {"ticket": ticket} if ticket else {"error": error or "failed"}
    if from_app and not ticket:
        params["app"] = "1"
    return get_settings().app_url.rstrip("/") + "/auth/apple/callback?" + urlencode(params)


@router.get("/status")
async def apple_status():
    return {"configured": configured()}


@router.post("/start")
async def start(payload: StartRequest, db: Session = Depends(get_db)):
    if not configured():
        raise HTTPException(status_code=503, detail="Sign in with Apple isn't set up yet")
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    if payload.app_proof_hash:
        state = APP_STATE_PREFIX + state
    now = datetime.utcnow()
    db.query(OAuthState).filter(OAuthState.expires_at < now).delete(synchronize_session=False)
    # Apple doesn't use PKCE here; the client secret and the one-time state protect the code
    db.add(OAuthState(state_hash=_hash(state), verifier="-", nonce=nonce, mode="apple",
                      next_path=safe_next(payload.next), app_proof_hash=payload.app_proof_hash,
                      expires_at=now + STATE_LIFETIME))
    db.commit()
    url = AUTHORIZE_URL + "?" + urlencode({
        "client_id": get_settings().apple_services_id, "redirect_uri": redirect_uri(), "response_type": "code",
        "response_mode": "form_post", "scope": "name email", "state": state, "nonce": nonce,
    })
    return {"url": url}


@router.post("/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    """Apple posts here (form fields: code, state, user the first time, or error)."""
    form = await request.form()
    state = str(form.get("state") or "")
    from_app = state.startswith(APP_STATE_PREFIX)
    pending = db.get(OAuthState, _hash(state)) if state else None
    if pending is None or pending.mode != "apple" or pending.expires_at < datetime.utcnow():
        return RedirectResponse(back_to_app_url(error="expired", from_app=from_app), status_code=303)
    nonce, next_path, proof_hash = pending.nonce, pending.next_path, pending.app_proof_hash
    # Used once, whatever happens next
    db.delete(pending)
    db.commit()

    if form.get("error"):
        reason = "cancelled" if form.get("error") == "user_cancelled_authorize" else "failed"
        return RedirectResponse(back_to_app_url(error=reason, from_app=from_app), status_code=303)
    code = str(form.get("code") or "")
    if not configured() or len(code) < 10:
        return RedirectResponse(back_to_app_url(error="failed", from_app=from_app), status_code=303)

    try:
        tokens = exchange_code(code)
        claims = id_token_claims(str(tokens.get("id_token") or ""))
        check_claims(claims, nonce)
    except (ValueError, HTTPException) as reason:
        logger.info("Apple sign-in refused: %s", reason)
        return RedirectResponse(back_to_app_url(error="failed", from_app=from_app), status_code=303)

    # Apple sends the name once, on the first sign-in
    try:
        name = (json.loads(str(form.get("user") or "{}")) or {}).get("name") or {}
    except ValueError:
        name = {}
    claims = {**claims, "given_name": name.get("firstName"), "family_name": name.get("lastName")}

    user, how = find_or_create_user(db, claims, provider="apple")
    if user.status == "deactivated":
        db.rollback()
        return RedirectResponse(back_to_app_url(error="closed", from_app=from_app), status_code=303)
    if user.status != "active" or not user.email_verified:
        # Apple has just confirmed this email belongs to them
        user.status, user.email_verified = "active", True
    if how == "linked":
        notify(db, user.id, "security", "Sign in with Apple added",
               f"You can now sign in to Hoardrun with Apple ({claims['email']}). If this wasn't you, contact support right away.",
               link="/security", key=f"apple-linked:{claims['sub']}")

    ticket = secrets.token_urlsafe(32)
    if from_app:
        ticket = APP_STATE_PREFIX + ticket
    db.add(AuthTicket(ticket_hash=_hash(ticket), user_id=user.id, new_user=how == "created", next_path=next_path,
                      app_proof_hash=proof_hash, expires_at=datetime.utcnow() + TICKET_LIFETIME))
    db.commit()
    return RedirectResponse(back_to_app_url(ticket=ticket), status_code=303)


@router.post("/redeem")
async def redeem(payload: RedeemRequest, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    db.query(AuthTicket).filter(AuthTicket.expires_at < now).delete(synchronize_session=False)
    ticket = db.get(AuthTicket, _hash(payload.ticket))
    if ticket is None or ticket.expires_at < now:
        db.commit()
        raise HTTPException(status_code=400, detail="That sign-in took too long or was already used. Try again.")
    user_id, new_user, next_path, proof_hash = ticket.user_id, ticket.new_user, ticket.next_path, ticket.app_proof_hash
    # Used once, whatever happens next
    db.delete(ticket)
    db.commit()
    if proof_hash is not None and (
            payload.app_proof is None or not secrets.compare_digest(_hash(payload.app_proof), proof_hash)):
        raise HTTPException(status_code=400, detail="Finish signing in with Apple in the Hoardrun app. Try again.")

    service = AuthService()
    user = await service._get_user_by_id(user_id, db)
    if user is None or user["status"] == "deactivated":
        raise HTTPException(status_code=403, detail="This account is closed.")
    login = await service.login_data_for(user, db)
    data = jsonable_encoder(login)
    data.update({"new_user": new_user, "next": next_path})
    return success_response(data=data, message="Signed in with Apple")
