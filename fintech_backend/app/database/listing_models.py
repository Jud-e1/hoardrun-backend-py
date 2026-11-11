"""
Businesses listed on the private equity, real estate and fixed income pages.

Anyone signed in can register a business (the startup registration form). It stays
private until a Hoardrun admin approves it; only approved listings are shown to other
people and can take investments. Nothing is seeded, so an empty table means an empty page.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, DECIMAL, ForeignKey, Integer, String, Text

from .config import Base


class CompanyListing(Base):
    """A business raising money, as described by the person who listed it."""
    __tablename__ = "company_listings"

    id = Column(String, primary_key=True)
    owner_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(80), nullable=False)
    category = Column(String(20), nullable=False, index=True)
    sector = Column(String(60), nullable=False)
    tagline = Column(String(160), nullable=False)
    about = Column(Text)
    location = Column(String(80))
    website = Column(String(200))
    founded_year = Column(Integer)

    funding_goal = Column(DECIMAL(18, 2), nullable=False)
    min_investment = Column(DECIMAL(18, 2), nullable=False)
    # What investors have put in through Hoardrun (see ListingInvestment)
    amount_raised = Column(DECIMAL(18, 2), nullable=False, default=0)
    target_return = Column(String(40))
    term = Column(String(40))
    risk_level = Column(String(12), nullable=False)

    # pending: waiting for an admin; approved: public and open to investment; rejected: kept private
    review_status = Column(String(10), nullable=False, default="pending", index=True)
    review_note = Column(String(300))
    reviewed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ListingInvestment(Base):
    """Money a person put into an approved listing, taken from their Hoardrun cash."""
    __tablename__ = "listing_investments"

    id = Column(String, primary_key=True)
    listing_id = Column(String, ForeignKey("company_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(DECIMAL(18, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
