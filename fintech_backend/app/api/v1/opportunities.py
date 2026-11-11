"""
Investment opportunities: businesses people registered (private equity, real estate,
fixed income), and investing in them.

A new listing waits for a Hoardrun admin (see admin_panel.py). Until it's approved only
the person who listed it can see it, with its review status; once approved it shows on
its category page and anyone except the owner can invest from their Hoardrun cash.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...auth.platform_admin import is_platform_admin
from ...database.config import get_db
from ...database.listing_models import CompanyListing, ListingInvestment
from ...database.models import User
from .circles import take_cash
from .venture import cash_balance

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

Category = Literal["private-equity", "real-estate", "fixed-income"]
RiskLevel = Literal["low", "moderate", "high", "very_high"]
CENT = Decimal("0.01")
CATEGORY_NAMES = {"private-equity": "private equity", "real-estate": "real estate", "fixed-income": "fixed income"}


class CompanyListingCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    category: Category
    sector: str = Field(min_length=2, max_length=60)
    tagline: str = Field(min_length=10, max_length=160)
    about: Optional[str] = Field(default=None, max_length=4000)
    location: Optional[str] = Field(default=None, max_length=80)
    website: Optional[str] = Field(default=None, max_length=200)
    founded_year: Optional[int] = None
    funding_goal: Decimal = Field(gt=0, le=Decimal("1000000000"))
    min_investment: Decimal = Field(gt=0)
    target_return: Optional[str] = Field(default=None, max_length=40)
    term: Optional[str] = Field(default=None, max_length=40)
    risk_level: RiskLevel

    @field_validator("name", "sector", "tagline", "about", "location", "website", "target_return", "term", mode="before")
    @classmethod
    def strip_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("website")
    @classmethod
    def check_website(cls, value):
        if value and not value.lower().startswith(("https://", "http://")):
            value = f"https://{value}"
        return value

    @field_validator("founded_year")
    @classmethod
    def check_founded_year(cls, value):
        if value is not None and not 1800 <= value <= datetime.utcnow().year:
            raise ValueError("Enter a real founding year")
        return value

    @model_validator(mode="after")
    def check_amounts(self):
        if self.min_investment > self.funding_goal:
            raise ValueError("The minimum investment can't be more than the amount being raised")
        return self


class InvestRequest(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("10000000"), decimal_places=2)


def money(value) -> float:
    return float(Decimal(value or 0).quantize(CENT))


def serialize(db: Session, listing: CompanyListing, user_id: str) -> dict:
    raised = Decimal(listing.amount_raised or 0)
    investors = db.query(func.count(func.distinct(ListingInvestment.user_id))).filter(ListingInvestment.listing_id == listing.id).scalar() or 0
    mine = db.query(func.coalesce(func.sum(ListingInvestment.amount), 0)).filter(
        ListingInvestment.listing_id == listing.id, ListingInvestment.user_id == user_id).scalar()
    is_owner = listing.owner_user_id == user_id
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
        "amount_raised": money(raised),
        "amount_left": money(max(Decimal(listing.funding_goal) - raised, Decimal(0))),
        "investor_count": int(investors),
        "my_investment": money(mine),
        "target_return": listing.target_return,
        "term": listing.term,
        "risk_level": listing.risk_level,
        "review_status": listing.review_status,
        # Why it wasn't approved: only the owner needs to know
        "review_note": listing.review_note if is_owner else None,
        "can_invest": listing.review_status == "approved" and not is_owner and raised < Decimal(listing.funding_goal),
        "created_at": listing.created_at.isoformat() + "Z",
        "is_owner": is_owner,
    }


def visible_listing(db: Session, listing_id: str, user_id: str) -> CompanyListing:
    """Approved listings are public; others only to their owner and admins."""
    listing = db.get(CompanyListing, listing_id)
    if listing is None or (
        listing.review_status != "approved" and listing.owner_user_id != user_id and not is_platform_admin(db.get(User, user_id))
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return listing


@router.get("")
async def list_opportunities(
    category: Optional[Category] = None,
    q: Optional[str] = Query(default=None, max_length=80),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Everyone sees approved listings; you also see your own while they wait for review
    query = db.query(CompanyListing).filter(or_(CompanyListing.review_status == "approved", CompanyListing.owner_user_id == user_id))
    if category:
        query = query.filter(CompanyListing.category == category)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(
            CompanyListing.name.ilike(term),
            CompanyListing.sector.ilike(term),
            CompanyListing.tagline.ilike(term),
            CompanyListing.location.ilike(term),
        ))
    listings = query.order_by(CompanyListing.created_at.desc()).limit(200).all()
    return {"data": [serialize(db, listing, user_id) for listing in listings], "total": len(listings),
            "cash_available": money(cash_balance(db, user_id))}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    payload: CompanyListingCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    listing = CompanyListing(id=str(uuid.uuid4()), owner_user_id=user_id, amount_raised=0, review_status="pending", **payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return {"data": serialize(db, listing, user_id)}


@router.get("/{listing_id}")
async def get_opportunity(
    listing_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    listing = visible_listing(db, listing_id, user_id)
    data = serialize(db, listing, user_id)
    data["cash_available"] = money(cash_balance(db, user_id))
    return {"data": data}


@router.post("/{listing_id}/invest")
async def invest(
    listing_id: str,
    payload: InvestRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    listing = db.query(CompanyListing).filter(CompanyListing.id == listing_id).with_for_update().first()
    if listing is None or listing.review_status != "approved":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This business isn't open for investment")
    if listing.owner_user_id == user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't invest in a business you listed")
    amount = payload.amount.quantize(CENT)
    left = Decimal(listing.funding_goal) - Decimal(listing.amount_raised or 0)
    if left <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This business has raised all it was looking for")
    if amount < Decimal(listing.min_investment) and amount < left:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"The smallest investment is ${Decimal(listing.min_investment):,.2f}")
    if amount > left:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Only ${left:,.2f} is left to raise")
    if not take_cash(db, user_id, amount, f"Invested in {listing.name}"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Not enough cash. You're investing ${amount:,.2f} and your Hoardrun cash is ${cash_balance(db, user_id):,.2f}. Add money first.",
        )
    listing.amount_raised = Decimal(listing.amount_raised or 0) + amount
    db.add(ListingInvestment(id=str(uuid.uuid4()), listing_id=listing.id, user_id=user_id, amount=amount))
    db.commit()
    data = serialize(db, listing, user_id)
    data["cash_available"] = money(cash_balance(db, user_id))
    return {"data": data}


@router.delete("/{listing_id}")
async def delete_opportunity(
    listing_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    listing = db.get(CompanyListing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    if listing.owner_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the person who listed this company can remove it")
    if db.query(ListingInvestment.id).filter(ListingInvestment.listing_id == listing_id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="People have invested in this business, so it can't be removed")
    db.delete(listing)
    db.commit()
    return {"data": {"id": listing_id, "deleted": True}}
