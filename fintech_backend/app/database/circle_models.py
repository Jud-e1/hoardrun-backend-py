"""
Investment circles: a group of people who decide together what to invest in.

Anyone can ask to join; the circle's admin (its creator) accepts or declines. Members
propose an investment (private equity, real estate, a venture fund and so on) and vote:
one person, one vote. It goes ahead only when more than half of the members say yes,
and never on one person's say-so. Members can also pool cash; each member's share of
fund holdings bought from the pool follows what they put in.
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
    # What the circle mainly invests in (an ASSET_TYPES key) and how many people it takes
    focus = Column(String(24))
    max_members = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CircleMember(Base):
    __tablename__ = "circle_members"
    __table_args__ = (UniqueConstraint("circle_id", "user_id", name="uq_circle_member"),)

    id = Column(String, primary_key=True)
    circle_id = Column(String, ForeignKey("investment_circles.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contributed = Column(DECIMAL(18, 2), nullable=False, default=0)
    # pending: asked to join and waiting for the admin; active: a member
    status = Column(String(10), nullable=False, default="active")
    requested_note = Column(String(200))
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CircleProposal(Base):
    """
    A member's proposal. kind "asset": everyone who votes yes puts in amount_per_member
    toward an investment of asset_type. kind "fund": buy venture fund shares from the pool.
    """
    __tablename__ = "circle_proposals"

    id = Column(String, primary_key=True)
    circle_id = Column(String, ForeignKey("investment_circles.id", ondelete="CASCADE"), nullable=False, index=True)
    proposer_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(8), nullable=False, default="fund")
    asset_type = Column(String(24))
    title = Column(String(80))
    amount_per_member = Column(DECIMAL(18, 2))
    fund_id = Column(String, ForeignKey("venture_funds.id"))
    shares = Column(Integer)
    amount = Column(DECIMAL(18, 2), nullable=False)
    note = Column(Text)
    # open, passed (invested), rejected, failed (passed but could not go ahead)
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


class CircleInvestment(Base):
    """One member's money in a passed asset proposal, taken from their cash when the vote passed."""
    __tablename__ = "circle_investments"
    __table_args__ = (UniqueConstraint("proposal_id", "user_id", name="uq_circle_investment"),)

    id = Column(String, primary_key=True)
    circle_id = Column(String, ForeignKey("investment_circles.id", ondelete="CASCADE"), nullable=False, index=True)
    proposal_id = Column(String, ForeignKey("circle_proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(DECIMAL(18, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
