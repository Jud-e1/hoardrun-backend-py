"""
The notification inbox: list, read, seen, delete. Notifications are created by features through
app.services.inbox.notify; this router only lets users manage their own.
"""

from datetime import datetime

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...database.config import get_db
from ...services.inbox import Notification, NotificationPrefs

router = APIRouter(prefix="/notifications", tags=["notifications"])


def note_out(note: Notification) -> dict:
    return {
        "id": note.id,
        "type": note.kind,
        "title": note.title,
        "message": note.message,
        "link": note.link,
        "timestamp": note.created_at.isoformat() + "Z",
        "read": note.read_at is not None,
        "seen": note.seen_at is not None,
    }


def mine(db: Session, user_id: str):
    return db.query(Notification).filter(Notification.user_id == user_id)


class PrefsUpdate(BaseModel):
    email: Optional[bool] = None
    marketing: Optional[bool] = None


def prefs_out(prefs: Optional[NotificationPrefs]) -> dict:
    # Security emails (a new sign-in method, a password change) always go out
    return {"email": True if prefs is None else prefs.email, "marketing": False if prefs is None else prefs.marketing,
            "security_always": True}


@router.get("/preferences")
async def get_preferences(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return prefs_out(db.get(NotificationPrefs, user_id))


@router.put("/preferences")
async def update_preferences(payload: PrefsUpdate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    prefs = db.get(NotificationPrefs, user_id)
    if prefs is None:
        prefs = NotificationPrefs(user_id=user_id, email=True, marketing=False)
        db.add(prefs)
    if payload.email is not None:
        prefs.email = payload.email
    if payload.marketing is not None:
        prefs.marketing = payload.marketing
    prefs.updated_at = datetime.utcnow()
    db.commit()
    return prefs_out(prefs)


@router.get("")
async def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    notes = mine(db, user_id).order_by(Notification.created_at.desc()).limit(limit).all()
    unread = mine(db, user_id).filter(Notification.read_at.is_(None)).count()
    return {"items": [note_out(n) for n in notes], "unread": unread}


@router.post("/{notification_id}/read")
async def mark_read(notification_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    note = mine(db, user_id).filter(Notification.id == notification_id).first()
    if note is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    now = datetime.utcnow()
    note.read_at = note.read_at or now
    note.seen_at = note.seen_at or now
    db.commit()
    return note_out(note)


@router.post("/read-all")
async def mark_all_read(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    updated = mine(db, user_id).filter(Notification.read_at.is_(None)).update(
        {Notification.read_at: now, Notification.seen_at: now}, synchronize_session=False
    )
    db.commit()
    return {"updated": updated}


@router.post("/seen")
async def mark_all_seen(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """The bell stops pulsing once the user has looked, without marking anything read."""
    updated = mine(db, user_id).filter(Notification.seen_at.is_(None)).update(
        {Notification.seen_at: datetime.utcnow()}, synchronize_session=False
    )
    db.commit()
    return {"updated": updated}


@router.delete("/{notification_id}")
async def delete_notification(notification_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    deleted = mine(db, user_id).filter(Notification.id == notification_id).delete(synchronize_session=False)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.commit()
    return {"deleted": True}


@router.delete("")
async def clear_all(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    deleted = mine(db, user_id).delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted}
