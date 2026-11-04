"""
Investment opportunities: companies that users have listed.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...database.config import get_db
from ...database.listing_models import CompanyListing

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

Category = Literal["private-equity", "real-estate", "fixed-income"]
RiskLevel = Literal["low", "moderate", "high", "very_high"]


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


def serialize(listing: CompanyListing, user_id: str) -> dict:
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
        "funding_goal": float(listing.funding_goal),
        "min_investment": float(listing.min_investment),
        "amount_raised": float(listing.amount_raised or 0),
        "target_return": listing.target_return,
        "term": listing.term,
        "risk_level": listing.risk_level,
        "created_at": listing.created_at.isoformat() + "Z",
        "is_owner": listing.owner_user_id == user_id,
    }


@router.get("")
async def list_opportunities(
    category: Optional[Category] = None,
    q: Optional[str] = Query(default=None, max_length=80),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    query = db.query(CompanyListing)
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
    return {"data": [serialize(listing, user_id) for listing in listings], "total": len(listings)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    payload: CompanyListingCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    listing = CompanyListing(id=str(uuid.uuid4()), owner_user_id=user_id, amount_raised=0, **payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return {"data": serialize(listing, user_id)}


@router.get("/{listing_id}")
async def get_opportunity(
    listing_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    listing = db.get(CompanyListing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return {"data": serialize(listing, user_id)}


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
    db.delete(listing)
    db.commit()
    return {"data": {"id": listing_id, "deleted": True}}
