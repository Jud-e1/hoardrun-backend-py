"""
Identity checks with Persona (an ID document and a selfie, on Persona's hosted page).

- /start creates a Persona inquiry for the user (or resumes their unfinished one) and returns
  the hosted verification URL. Persona sends the person back to APP_URL/face-verification.
- The result is only ever read from Persona's API: when the person comes back (/refresh) and
  when Persona's webhook says something changed. The webhook must be signed with the webhook
  secret; nothing in a redirect or webhook body is trusted on its own.
- Sending money to others and withdrawing to a bank need a verified identity whenever checks
  are set up, and always in production (require_verified_identity).
"""

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...auth.signing_key import is_production
from ...config.settings import get_settings
from ...database.config import Base, get_db
from ...database.models import User
from ...services.inbox import notify

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/identity", tags=["identity"])

API = "https://api.withpersona.com/api/v1"
HOSTED = "https://withpersona.com/verify"
API_VERSION = "2023-01-05"
SIGNATURE_TOLERANCE = 300

# Persona's inquiry status, in the app's words
STATES = {
    "created": "in_progress", "pending": "in_progress",
    "completed": "verified", "approved": "verified",
    "needs_review": "in_review",
    "declined": "declined", "failed": "declined",
    "expired": "not_started",
}
# A new inquiry can be started from these
RESTARTABLE = {"not_started", "declined"}


class IdentityCheck(Base):
    """A user's latest Persona inquiry and what it came to."""
    __tablename__ = "identity_checks"

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    inquiry_id = Column(String(60), unique=True, nullable=False)
    persona_status = Column(String(20), nullable=False, default="created")
    state = Column(String(20), nullable=False, default="in_progress")
    verified_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ---------- Persona ----------

def configured() -> bool:
    settings = get_settings()
    return bool(settings.persona_api_key and settings.persona_template_id)


def persona_call(method: str, path: str, body: Optional[dict] = None) -> dict:
    """One Persona API request. Tests replace this."""
    settings = get_settings()
    try:
        response = httpx.request(method, API + path, json=body, timeout=15, headers={
            "Authorization": f"Bearer {settings.persona_api_key}", "Persona-Version": API_VERSION,
            "Key-Inflection": "kebab", "Accept": "application/json",
        })
    except httpx.HTTPError as error:
        logger.warning("Persona unreachable: %s", error)
        raise HTTPException(status_code=502, detail="The identity check service didn't respond. Try again.")
    if response.status_code >= 400:
        logger.warning("Persona %s %s failed: %s %s", method, path, response.status_code, response.text[:300])
        raise HTTPException(status_code=502, detail="The identity check service didn't accept that. Try again.")
    return response.json()


def hosted_url(inquiry_id: str, session_token: Optional[str] = None) -> str:
    params = {"inquiry-id": inquiry_id, "redirect-uri": get_settings().app_url.rstrip("/") + "/face-verification?done=1"}
    if session_token:
        params["session-token"] = session_token
    return HOSTED + "?" + urlencode(params)


def signature_ok(raw: bytes, header: str) -> bool:
    """Persona-Signature: t=<unix time>,v1=<hex>[ v1=<hex> during secret rotation]."""
    secret = get_settings().persona_webhook_secret
    if not secret or not header:
        return False
    timestamp, signatures = None, []
    for part in header.replace(" ", ",").split(","):
        key, _, value = part.partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1" and value:
            signatures.append(value)
    if not timestamp or not timestamp.isdigit() or abs(time.time() - int(timestamp)) > SIGNATURE_TOLERANCE:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + raw, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, signature) for signature in signatures)


# ---------- State ----------

def apply_status(db: Session, check: IdentityCheck, persona_status: str) -> None:
    """Record Persona's status; tell the person once when it's decided."""
    persona_status = (persona_status or "").lower()
    state = STATES.get(persona_status, "in_progress")
    before = check.state
    check.persona_status, check.state, check.updated_at = persona_status, state, datetime.utcnow()
    user = db.get(User, check.user_id)
    if state == "verified" and before != "verified":
        check.verified_at = datetime.utcnow()
        if user is not None:
            user.is_verified = True
        notify(db, check.user_id, "success", "Identity verified",
               "Thanks. Your identity is confirmed, so sending money and withdrawals are open to you.",
               link="/home", key=f"identity-verified:{check.inquiry_id}", email=True)
    elif state == "declined" and before != "declined":
        if user is not None:
            user.is_verified = False
        notify(db, check.user_id, "warning", "We couldn't verify your identity",
               "Your identity check didn't go through. You can try again with a clear photo of a valid ID.",
               link="/face-verification", key=f"identity-declined:{check.inquiry_id}", email=True)


def refresh_from_persona(db: Session, check: IdentityCheck) -> None:
    inquiry = persona_call("GET", f"/inquiries/{check.inquiry_id}")
    attributes = (inquiry.get("data") or {}).get("attributes") or {}
    if attributes.get("reference-id") not in (None, check.user_id):
        logger.error("Persona inquiry %s belongs to a different reference", check.inquiry_id)
        return
    apply_status(db, check, attributes.get("status") or "")
    db.commit()


def show(check: Optional[IdentityCheck]) -> dict:
    state = check.state if check else "not_started"
    return {
        "state": state, "configured": configured(), "can_start": state in RESTARTABLE or state == "in_progress",
        "verified_at": check.verified_at.isoformat() + "Z" if check and check.verified_at else None,
    }


def checks_required() -> bool:
    return configured() or is_production()


def require_verified_identity(db: Session, user_id: str, action: str) -> None:
    """Refuse an action that moves money away from the person until their identity is verified."""
    if not checks_required():
        return
    check = db.get(IdentityCheck, user_id)
    if check is None or check.state != "verified":
        raise HTTPException(status_code=403, detail=f"Verify your identity to {action}. It takes about two minutes.")


# ---------- Routes ----------

@router.get("/status")
async def status(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return show(db.get(IdentityCheck, user_id))


@router.post("/start")
async def start(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    if not configured():
        raise HTTPException(status_code=503, detail="Identity checks aren't set up yet")
    check = db.get(IdentityCheck, user_id)
    if check is not None and check.state == "verified":
        raise HTTPException(status_code=409, detail="Your identity is already verified.")
    if check is not None and check.state == "in_review":
        raise HTTPException(status_code=409, detail="Your identity check is being reviewed. We'll email you when it's done.")

    if check is not None and check.state == "in_progress":
        # Pick up where they left off
        resumed = persona_call("POST", f"/inquiries/{check.inquiry_id}/resume")
        return {"url": hosted_url(check.inquiry_id, (resumed.get("meta") or {}).get("session-token"))}

    user = db.get(User, user_id)
    fields = {"email-address": user.email} if user else {}
    if user and user.first_name:
        fields["name-first"] = user.first_name
    if user and user.last_name and user.last_name != "-":
        fields["name-last"] = user.last_name
    created = persona_call("POST", "/inquiries", {"data": {"attributes": {
        "inquiry-template-id": get_settings().persona_template_id, "reference-id": user_id, "fields": fields,
    }}})
    inquiry_id = created["data"]["id"]
    if check is None:
        check = IdentityCheck(user_id=user_id, inquiry_id=inquiry_id)
        db.add(check)
    check.inquiry_id, check.persona_status, check.state = inquiry_id, "created", "in_progress"
    check.verified_at, check.updated_at = None, datetime.utcnow()
    db.commit()
    return {"url": hosted_url(inquiry_id, (created.get("meta") or {}).get("session-token"))}


@router.post("/refresh")
async def refresh(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """After Persona sends the person back: ask Persona how it went."""
    check = db.get(IdentityCheck, user_id)
    if check is not None and configured() and check.state not in ("verified",):
        refresh_from_persona(db, check)
    return show(check)


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    if not signature_ok(raw, request.headers.get("persona-signature", "")):
        raise HTTPException(status_code=400, detail="Invalid signature")
    try:
        event = json.loads(raw)
        payload = event["data"]["attributes"]["payload"]["data"]
    except (ValueError, KeyError, TypeError):
        return {"received": True}
    if payload.get("type") != "inquiry":
        return {"received": True}
    check = db.query(IdentityCheck).filter(IdentityCheck.inquiry_id == str(payload.get("id"))).first()
    if check is not None and configured():
        refresh_from_persona(db, check)
    return {"received": True}
