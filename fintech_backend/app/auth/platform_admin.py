"""
Who runs Hoardrun: the people allowed into the admin area (overview, users, business approvals).

A person is an admin when their account's role is "admin", or their email is listed in
PLATFORM_ADMIN_EMAILS (comma separated). The email list lets the owner be made admin
without editing the database.
"""

import os

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database.config import get_db
from ..database.models import User
from .dependencies import get_current_user_id


def admin_emails() -> set:
    raw = os.getenv("PLATFORM_ADMIN_EMAILS", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def is_platform_admin(user: User | None) -> bool:
    if user is None or not user.is_active:
        return False
    return user.role == "admin" or (user.email or "").strip().lower() in admin_emails()


def require_platform_admin(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if not is_platform_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Hoardrun admins can see this")
    return user
