"""
Companies listed on the investment opportunities page.

Every row is a company a signed-in user listed. Nothing is seeded, so an empty
table means an empty page.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, DECIMAL, ForeignKey, Integer, String, Text

from .config import Base


class CompanyListing(Base):
    """A company raising money, as described by the person who listed it."""
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
    # Only investments made through Hoardrun would raise this, and there is no investing flow yet
    amount_raised = Column(DECIMAL(18, 2), nullable=False, default=0)
    target_return = Column(String(40))
    term = Column(String(40))
    risk_level = Column(String(12), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
