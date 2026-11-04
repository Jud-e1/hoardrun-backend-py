"""
Investment circles: people pool cash, vote on what to buy, and own the result in
proportion to what they put in.

Each member's stake is the cash they contributed. Stakes decide both voting power
and each member's share of everything the circle holds.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, DECIMAL, ForeignKey, Integer, String, Text, UniqueConstraint

from .config import Base


class InvestmentCircle(Base):
    __tablename__ = "investment_circles"

    id = Column(String, primary_key=True)
    creator_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(60), nullable=False)
    purpose = Column(String(160), nullable=False)
    min_contribution = Column(DECIMAL(18, 2), nullable=False)
    # Cash contributed and not yet spent on investments
    pool_balance = Column(DECIMAL(18, 2), nullable=False, default=0)
    # Sum of every member's stake
    total_contributed = Column(DECIMAL(18, 2), nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CircleMember(Base):
    __tablename__ = "circle_members"
    __table_args__ = (UniqueConstraint("circle_id", "user_id", name="uq_circle_member"),)

    id = Column(String, primary_key=True)
    circle_id = Column(String, ForeignKey("investment_circles.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contributed = Column(DECIMAL(18, 2), nullable=False, default=0)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CircleProposal(Base):
    """A member's proposal to spend pooled cash on shares in a venture fund."""
    __tablename__ = "circle_proposals"

    id = Column(String, primary_key=True)
    circle_id = Column(String, ForeignKey("investment_circles.id", ondelete="CASCADE"), nullable=False, index=True)
    proposer_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    fund_id = Column(String, ForeignKey("venture_funds.id"), nullable=False)
    shares = Column(Integer, nullable=False)
    amount = Column(DECIMAL(18, 2), nullable=False)
    note = Column(Text)
    # open, passed (bought), rejected, failed (passed but could not be bought)
    status = Column(String(12), nullable=False, default="open")
    outcome = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    decided_at = Column(DateTime)


class CircleVote(Base):
    __tablename__ = "circle_votes"
    __table_args__ = (UniqueConstraint("proposal_id", "user_id", name="uq_circle_vote"),)

    id = Column(String, primary_key=True)
    proposal_id = Column(String, ForeignKey("circle_proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    choice = Column(String(3), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CircleHolding(Base):
    """Fund shares the circle owns together, bought by a passed proposal."""
    __tablename__ = "circle_holdings"

    id = Column(String, primary_key=True)
    circle_id = Column(String, ForeignKey("investment_circles.id", ondelete="CASCADE"), nullable=False, index=True)
    fund_id = Column(String, ForeignKey("venture_funds.id"), nullable=False)
    proposal_id = Column(String, ForeignKey("circle_proposals.id"), nullable=False)
    shares = Column(Integer, nullable=False)
    amount = Column(DECIMAL(18, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
