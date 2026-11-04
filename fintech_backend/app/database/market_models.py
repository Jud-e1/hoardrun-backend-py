"""
Crypto and ETF positions held on Hoardrun's own books, and the orders that changed them.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, DECIMAL, ForeignKey, String, UniqueConstraint

from .config import Base


class MarketPosition(Base):
    __tablename__ = "market_positions"
    __table_args__ = (UniqueConstraint("user_id", "asset_type", "symbol", name="uq_market_position"),)

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type = Column(String(8), nullable=False)
    symbol = Column(String(12), nullable=False)
    quantity = Column(DECIMAL(28, 10), nullable=False, default=0)
    # What the remaining quantity cost, so gains can be shown
    cost_basis = Column(DECIMAL(18, 2), nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class MarketOrder(Base):
    __tablename__ = "market_orders"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type = Column(String(8), nullable=False)
    symbol = Column(String(12), nullable=False)
    side = Column(String(4), nullable=False)
    quantity = Column(DECIMAL(28, 10), nullable=False)
    price = Column(DECIMAL(18, 8), nullable=False)
    amount = Column(DECIMAL(18, 2), nullable=False)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
