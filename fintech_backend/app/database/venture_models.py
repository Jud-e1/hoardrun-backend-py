"""
Venture funds that firms register, and the shares people buy in them.

A fund is split into a fixed number of equal shares at one price, so buying
shares works like buying units of an index fund. Nothing is seeded.
"""

from datetime import datetime

from sqlalchemy import JSON, Column, Date, DateTime, DECIMAL, ForeignKey, Integer, String, Text

from .config import Base


class VentureFund(Base):
    __tablename__ = "venture_funds"

    id = Column(String, primary_key=True)
    manager_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    firm_name = Column(String(80), nullable=False)
    fund_name = Column(String(80), nullable=False)
    thesis = Column(String(160), nullable=False)
    about = Column(Text)
    sectors = Column(JSON, nullable=False, default=list)
    stage = Column(String(20), nullable=False)
    location = Column(String(80))
    website = Column(String(200))

    share_price = Column(DECIMAL(18, 2), nullable=False)
    total_shares = Column(Integer, nullable=False)
    min_shares = Column(Integer, nullable=False, default=1)
    shares_sold = Column(Integer, nullable=False, default=0)
    term_years = Column(Integer, nullable=False)
    management_fee = Column(DECIMAL(5, 2), nullable=False)
    carry = Column(DECIMAL(5, 2), nullable=False)
    closes_on = Column(Date)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FundShareOrder(Base):
    """One purchase of shares, paid from the buyer's Hoardrun cash account."""
    __tablename__ = "fund_share_orders"

    id = Column(String, primary_key=True)
    fund_id = Column(String, ForeignKey("venture_funds.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)

    shares = Column(Integer, nullable=False)
    share_price = Column(DECIMAL(18, 2), nullable=False)
    amount = Column(DECIMAL(18, 2), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
