"""
In-app notifications, stored per user.

Features call notify() inside their own database transaction, so a notification exists
exactly when the event it describes was committed. A key makes an event notify only once.

Security notifications are also emailed, always. Others are emailed when the feature asks
(email=True) and the person hasn't turned email off; the email goes out after the commit.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Session

from ..database.config import Base

KINDS = {"info", "success", "warning", "error", "transaction", "security"}


class NotificationPrefs(Base):
    """How a person wants to hear about things beyond the in-app list. No row means the defaults."""
    __tablename__ = "notification_prefs"

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    email = Column(Boolean, nullable=False, default=True)
    marketing = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


def wants_email(db: Session, user_id: str) -> bool:
    prefs = db.get(NotificationPrefs, user_id)
    return True if prefs is None else bool(prefs.email)


def _email(db: Session, user_id: str, kind: str, title: str, message: str, link: Optional[str]) -> None:
    from ..database.models import User
    from .email_service import event_email, queue

    if kind != "security" and not wants_email(db, user_id):
        return
    user = db.get(User, user_id)
    if user is None or not user.email or user.status == "deactivated":
        return
    queue(db, user.email, *event_email(title, message, link))


class Notification(Base):
    __tablename__ = "user_notifications"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_notification_key"),)

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(12), nullable=False, default="info")
    title = Column(String(120), nullable=False)
    message = Column(String(400), nullable=False)
    # An app path the notification opens, such as /savings
    link = Column(String(120))
    dedupe_key = Column(String(120))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at = Column(DateTime)
    seen_at = Column(DateTime)


def notify(
    db: Session,
    user_id: str,
    kind: str,
    title: str,
    message: str,
    *,
    link: Optional[str] = None,
    key: Optional[str] = None,
    email: bool = False,
) -> Optional[Notification]:
    """Queue a notification in the caller's transaction. Returns None when this key already notified."""
    if kind not in KINDS:
        kind = "info"
    if key is not None:
        pending = [n for n in db.new if isinstance(n, Notification) and n.user_id == user_id and n.dedupe_key == key]
        if pending or db.query(Notification.id).filter(Notification.user_id == user_id, Notification.dedupe_key == key).first():
            return None
    note = Notification(
        id=str(uuid.uuid4()), user_id=user_id, kind=kind, title=title[:120], message=message[:400], link=link, dedupe_key=key,
    )
    db.add(note)
    if email or kind == "security":
        _email(db, user_id, kind, note.title, note.message, link)
    return note
