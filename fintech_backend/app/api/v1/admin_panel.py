"""
The Hoardrun admin area: what's happening across the whole app, who has signed up, and
the business listings waiting for approval before they appear on the private equity,
real estate and fixed income pages.

Only platform admins get in (see auth/platform_admin.py); everyone else gets 403.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...auth.platform_admin import is_platform_admin, require_platform_admin
from ...database.circle_models import CircleInvestment, CircleMember, InvestmentCircle
from ...database.config import get_db
from ...database.listing_models import CompanyListing, ListingInvestment
from ...database.models import Account, Transaction, TransactionDirectionEnum, TransactionStatusEnum, TransactionTypeEnum, User
from ...database.venture_models import FundShareOrder
from ...services.inbox import notify

router = APIRouter(prefix="/admin-panel", tags=["admin-panel"])

CENT = Decimal("0.01")
CATEGORY_NAMES = {"private-equity": "private equity", "real-estate": "real estate", "fixed-income": "fixed income"}


class Review(BaseModel):
    note: Optional[str] = Field(default=None, max_length=300)


def money(value) -> float:
    return float(Decimal(value or 0).quantize(CENT))


def total(db: Session, column, *filters) -> float:
    return money(db.query(func.coalesce(func.sum(column), 0)).filter(*filters).scalar())


def iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


def full_name(user: Optional[User]) -> str:
    if user is None:
        return "Deleted user"
    return f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip() or user.email


@router.get("/me")
async def me(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Whether the signed-in person may open the admin area (the app uses it to show the link)."""
    return {"is_admin": is_platform_admin(db.get(User, user_id))}


@router.get("/overview")
async def overview(admin: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    day, week, month = now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=30)
    users = db.query(User)
    completed = Transaction.status == TransactionStatusEnum.COMPLETED

    # Sign-ups per day for the last 14 days
    since = (now - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0)
    per_day = {}
    for (created,) in db.query(User.created_at).filter(User.created_at >= since):
        if created is not None:
            key = created.date().isoformat()
            per_day[key] = per_day.get(key, 0) + 1
    signups = [{"date": (since + timedelta(days=offset)).date().isoformat(),
                "count": per_day.get((since + timedelta(days=offset)).date().isoformat(), 0)} for offset in range(14)]

    listings = dict(db.query(CompanyListing.review_status, func.count(CompanyListing.id)).group_by(CompanyListing.review_status).all())
    return {"data": {
        "users": {
            "total": users.count(),
            "new_today": users.filter(User.created_at >= day).count(),
            "new_7_days": users.filter(User.created_at >= week).count(),
            "new_30_days": users.filter(User.created_at >= month).count(),
            "verified_email": users.filter(User.email_verified.is_(True)).count(),
            "active_7_days": users.filter(User.last_login_at >= week).count(),
            "signups_14_days": signups,
        },
        "money": {
            "cash_held": total(db, Account.current_balance, Account.currency == "USD"),
            "deposits_30_days": total(db, Transaction.amount, completed, Transaction.transaction_type == TransactionTypeEnum.DEPOSIT, Transaction.created_at >= month),
            "transactions_30_days": db.query(Transaction).filter(Transaction.created_at >= month).count(),
            "sent_30_days": total(db, Transaction.amount, completed, Transaction.direction == TransactionDirectionEnum.OUTBOUND, Transaction.created_at >= month),
        },
        "investing": {
            "listings_pending": int(listings.get("pending", 0)),
            "listings_approved": int(listings.get("approved", 0)),
            "listings_rejected": int(listings.get("rejected", 0)),
            "invested_in_listings": total(db, ListingInvestment.amount),
            "listing_investors": db.query(func.count(func.distinct(ListingInvestment.user_id))).scalar() or 0,
            "circles": db.query(InvestmentCircle).count(),
            "circle_members": db.query(CircleMember).filter(CircleMember.status == "active").count(),
            "invested_by_circles": total(db, CircleInvestment.amount) + total(db, CircleMember.contributed),
            "venture_fund_orders": total(db, FundShareOrder.amount),
        },
    }}


@router.get("/users")
async def users(
    q: Optional[str] = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    size = 25
    query = db.query(User)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(User.email.ilike(term), User.first_name.ilike(term), User.last_name.ilike(term)))
    count = query.count()
    rows = query.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size).all()
    ids = [u.id for u in rows]
    cash = dict(db.query(Account.user_id, func.coalesce(func.sum(Account.current_balance), 0))
                .filter(Account.user_id.in_(ids), Account.currency == "USD").group_by(Account.user_id).all()) if ids else {}
    return {"data": [
        {
            "id": u.id,
            "name": full_name(u),
            "email": u.email,
            "joined_at": iso(u.created_at),
            "last_login_at": iso(u.last_login_at),
            "email_verified": bool(u.email_verified),
            "status": u.status,
            "is_admin": is_platform_admin(u),
            "cash": money(cash.get(u.id, 0)),
        }
        for u in rows
    ], "total": count, "page": page, "pages": max((count + size - 1) // size, 1)}


@router.get("/listings")
async def listings(
    review_status: Literal["pending", "approved", "rejected", "all"] = Query(default="pending", alias="status"),
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    query = db.query(CompanyListing)
    if review_status != "all":
        query = query.filter(CompanyListing.review_status == review_status)
    rows = query.order_by(CompanyListing.created_at.desc()).limit(200).all()
    owners = {u.id: u for u in db.query(User).filter(User.id.in_({r.owner_user_id for r in rows}))} if rows else {}
    return {"data": [listing_out(db, listing, owners.get(listing.owner_user_id)) for listing in rows]}


def listing_out(db: Session, listing: CompanyListing, owner: Optional[User]) -> dict:
    return {
        "id": listing.id,
        "name": listing.name,
        "category": listing.category,
        "sector": listing.sector,
        "tagline": listing.tagline,
        "about": listing.about,
        "location": listing.location,
        "website": listing.website,
        "founded_year": listing.founded_year,
        "funding_goal": money(listing.funding_goal),
        "min_investment": money(listing.min_investment),
        "amount_raised": money(listing.amount_raised),
        "target_return": listing.target_return,
        "term": listing.term,
        "risk_level": listing.risk_level,
        "review_status": listing.review_status,
        "review_note": listing.review_note,
        "reviewed_at": iso(listing.reviewed_at),
        "created_at": iso(listing.created_at),
        "owner": {"name": full_name(owner), "email": owner.email if owner else None,
                  "email_verified": bool(owner.email_verified) if owner else False, "joined_at": iso(owner.created_at) if owner else None},
        "investor_count": db.query(func.count(func.distinct(ListingInvestment.user_id))).filter(ListingInvestment.listing_id == listing.id).scalar() or 0,
    }


@router.post("/listings/{listing_id}/{decision}")
async def review_listing(
    listing_id: str,
    decision: Literal["approve", "reject"],
    payload: Optional[Review] = None,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    listing = db.query(CompanyListing).filter(CompanyListing.id == listing_id).with_for_update().first()
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    note = ((payload.note or "").strip() or None) if payload else None
    if decision == "reject" and listing.amount_raised and Decimal(listing.amount_raised) > 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="People have already invested in this business, so it can't be taken down here")
    page = CATEGORY_NAMES.get(listing.category, "investments")
    listing.review_status = "approved" if decision == "approve" else "rejected"
    listing.review_note = note
    listing.reviewed_by = admin.id
    listing.reviewed_at = datetime.utcnow()
    if decision == "approve":
        notify(db, listing.owner_user_id, "success", f"{listing.name} is live",
               f"Hoardrun approved your listing. It's now on the {page} page and people can invest.",
               link=f"/investment-opportunities?category={listing.category}", email=True)
    else:
        notify(db, listing.owner_user_id, "info", f"{listing.name} wasn't approved",
               note or "Hoardrun couldn't approve your listing. Check the details and list it again.",
               link=f"/investment-opportunities?category={listing.category}", email=True)
    db.commit()
    owner = db.get(User, listing.owner_user_id)
    return {"data": listing_out(db, listing, owner)}
