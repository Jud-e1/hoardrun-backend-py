"""
One-time secrets sent by email: 6-digit sign-up codes and password reset links.

Only a hash is stored. A code works for one account (it's checked together with the email),
expires, allows a few wrong tries, and works once. Asking again within a minute reuses the
wait instead of sending another email, so nobody can flood an inbox.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Session

from ..database.config import Base
from ..database.models import User

VERIFY = "verify"
RESET = "reset"
LIFETIME = {VERIFY: timedelta(hours=24), RESET: timedelta(hours=1)}
MAX_TRIES = 5
RESEND_AFTER = timedelta(seconds=60)


class AuthCode(Base):
    __tablename__ = "auth_codes"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String(10), nullable=False)
    secret_hash = Column(String(64), nullable=False, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class CodeError(Exception):
    """Why a code or link didn't work, in words the person can act on."""


def _hash(purpose: str, user_id: str, secret: str) -> str:
    return hashlib.sha256(f"{purpose}:{user_id}:{secret}".encode("utf-8")).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(f"{RESET}:{token}".encode("utf-8")).hexdigest()


def _live(db: Session, user_id: str, purpose: str) -> Optional[AuthCode]:
    return (
        db.query(AuthCode)
        .filter(AuthCode.user_id == user_id, AuthCode.purpose == purpose, AuthCode.used_at.is_(None),
                AuthCode.expires_at > datetime.utcnow())
        .order_by(AuthCode.created_at.desc()).first()
    )


def too_soon(db: Session, user_id: str, purpose: str) -> bool:
    latest = _live(db, user_id, purpose)
    return latest is not None and datetime.utcnow() - latest.created_at < RESEND_AFTER


def _replace(db: Session, user_id: str, purpose: str, secret_hash: str) -> None:
    now = datetime.utcnow()
    # Only the newest code works
    db.query(AuthCode).filter(AuthCode.user_id == user_id, AuthCode.purpose == purpose,
                              AuthCode.used_at.is_(None)).update({AuthCode.used_at: now})
    db.add(AuthCode(id=str(uuid.uuid4()), user_id=user_id, purpose=purpose, secret_hash=secret_hash,
                    expires_at=now + LIFETIME[purpose], created_at=now))
    db.commit()


def issue_verification_code(db: Session, user_id: str) -> str:
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    _replace(db, user_id, VERIFY, _hash(VERIFY, user_id, code))
    return code


def check_verification_code(db: Session, email: str, code: str) -> User:
    """The user whose code this is. Raises CodeError otherwise."""
    user = db.query(User).filter(User.email == (email or "").strip().lower()).first()
    if user is None:
        user = db.query(User).filter(User.email == (email or "").strip()).first()
    live = _live(db, user.id, VERIFY) if user else None
    if user is None or live is None:
        raise CodeError("That code has expired. Ask for a new one.")
    if live.attempts >= MAX_TRIES:
        raise CodeError("Too many wrong tries. Ask for a new code.")
    if not secrets.compare_digest(live.secret_hash, _hash(VERIFY, user.id, (code or "").strip())):
        live.attempts += 1
        db.commit()
        left = MAX_TRIES - live.attempts
        raise CodeError(f"That code isn't right. {left} tr{'y' if left == 1 else 'ies'} left." if left else
                        "Too many wrong tries. Ask for a new code.")
    live.used_at = datetime.utcnow()
    db.commit()
    return user


def issue_reset_token(db: Session, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    _replace(db, user_id, RESET, _token_hash(token))
    return token


def use_reset_token(db: Session, token: str) -> User:
    """The user a reset link belongs to; the link stops working. Raises CodeError otherwise."""
    row = db.query(AuthCode).filter(AuthCode.purpose == RESET, AuthCode.secret_hash == _token_hash(token or "")).first()
    if row is None or row.used_at is not None or row.expires_at <= datetime.utcnow():
        raise CodeError("This reset link has expired or was already used. Ask for a new one.")
    user = db.get(User, row.user_id)
    if user is None:
        raise CodeError("This reset link has expired or was already used. Ask for a new one.")
    row.used_at = datetime.utcnow()
    return user


def reset_token_is_live(db: Session, token: str) -> bool:
    row = db.query(AuthCode).filter(AuthCode.purpose == RESET, AuthCode.secret_hash == _token_hash(token or "")).first()
    return row is not None and row.used_at is None and row.expires_at > datetime.utcnow()
