"""
Locking sign-in after repeated wrong passwords, per email address.

Five wrong passwords within 15 minutes lock password sign-in for that email for 15 minutes,
whichever server process the attempts reach (it's stored in the database). The email is kept
only as a hash, so the table doesn't become a list of who tried to sign in. A correct password
clears the count; a password reset ends a lock early.
"""

import hashlib
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import Session

from ..database.config import Base

MAX_FAILURES = 5
WINDOW = timedelta(minutes=15)
LOCK_FOR = timedelta(minutes=15)


class LoginThrottle(Base):
    __tablename__ = "login_throttle"

    email_hash = Column(String(64), primary_key=True)
    failures = Column(Integer, nullable=False, default=0)
    first_failure_at = Column(DateTime, nullable=False)
    locked_until = Column(DateTime)


def _key(email: str) -> str:
    return hashlib.sha256((email or "").strip().lower().encode("utf-8")).hexdigest()


def locked_for(db: Session, email: str) -> Optional[timedelta]:
    """How much longer sign-in is locked for this email, or None."""
    row = db.get(LoginThrottle, _key(email))
    now = datetime.utcnow()
    if row is None or row.locked_until is None or row.locked_until <= now:
        return None
    return row.locked_until - now


def record_failure(db: Session, email: str) -> bool:
    """Count a wrong password. Returns True when this one locks the account."""
    now = datetime.utcnow()
    row = db.get(LoginThrottle, _key(email))
    if row is None or now - row.first_failure_at > WINDOW:
        if row is None:
            row = LoginThrottle(email_hash=_key(email), failures=0, first_failure_at=now)
            db.add(row)
        row.failures, row.first_failure_at, row.locked_until = 0, now, None
    row.failures += 1
    locked = row.failures >= MAX_FAILURES
    if locked:
        row.locked_until = now + LOCK_FOR
    db.commit()
    return locked


def clear(db: Session, email: str) -> None:
    row = db.get(LoginThrottle, _key(email))
    if row is not None:
        db.delete(row)
        db.commit()
