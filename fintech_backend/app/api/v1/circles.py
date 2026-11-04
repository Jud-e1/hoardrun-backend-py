"""
Investment circles: pool Hoardrun cash with other people, vote on buying venture
fund shares, and own the result in proportion to what each person put in.

Voting power is each member's contribution as a share of the circle's total, so the
biggest contributors carry the most weight. A proposal is bought the moment "yes"
passes half of all contributions, and rejected once "no" reaches half.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...database.circle_models import CircleHolding, CircleMember, CircleProposal, CircleVote, InvestmentCircle
from ...database.config import get_db
from ...database.models import (
    Account, PaymentMethodEnum, Transaction, TransactionDirectionEnum, TransactionStatusEnum,
    TransactionTypeEnum, User,
)
from ...database.venture_models import VentureFund
from .venture import cash_accounts, cash_balance, get_fund, is_open

router = APIRouter(prefix="/circles", tags=["circles"])

CENT = Decimal("0.01")


class CircleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    purpose: str = Field(min_length=10, max_length=160)
    min_contribution: Decimal = Field(ge=Decimal("1"), le=Decimal("1000000"), decimal_places=2)


class Contribution(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("10000000"), decimal_places=2)


class ProposalCreate(BaseModel):
    fund_id: str
    shares: int = Field(ge=1, le=10_000_000)
    note: Optional[str] = Field(default=None, max_length=500)


class VoteCast(BaseModel):
    choice: Literal["yes", "no"]


def money(value) -> float:
    return float(Decimal(value or 0).quantize(CENT))


def display_name(user: Optional[User]) -> str:
    if user is None:
        return "Member"
    last = (user.last_name or "").strip()
    return f"{(user.first_name or 'Member').strip()} {last[:1] + '.' if last else ''}".strip()


def get_circle(db: Session, circle_id: str, lock: bool = False) -> InvestmentCircle:
    query = db.query(InvestmentCircle).filter(InvestmentCircle.id == circle_id)
    if lock:
        query = query.with_for_update()
    circle = query.first()
    if circle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circle not found")
    return circle


def membership(db: Session, circle_id: str, user_id: str) -> Optional[CircleMember]:
    return db.query(CircleMember).filter_by(circle_id=circle_id, user_id=user_id).first()


def require_member(db: Session, circle_id: str, user_id: str) -> CircleMember:
    member = membership(db, circle_id, user_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Join the circle first")
    return member


def tally(db: Session, proposal: CircleProposal, total: Decimal) -> dict:
    stakes = {m.user_id: Decimal(m.contributed) for m in db.query(CircleMember).filter_by(circle_id=proposal.circle_id)}
    yes = no = Decimal(0)
    votes = []
    for vote in db.query(CircleVote).filter_by(proposal_id=proposal.id):
        weight = stakes.get(vote.user_id, Decimal(0))
        if vote.choice == "yes":
            yes += weight
        else:
            no += weight
        votes.append(vote)
    share = lambda part: float(part / total) if total > 0 else 0.0  # noqa: E731
    return {"yes": share(yes), "no": share(no), "yes_amount": yes, "no_amount": no, "votes": votes}


def settle(db: Session, circle: InvestmentCircle, proposal: CircleProposal) -> None:
    """Buy or reject an open proposal once its vote is decided."""
    if proposal.status != "open":
        return
    total = Decimal(circle.total_contributed)
    result = tally(db, proposal, total)
    now = datetime.now(timezone.utc)
    if total > 0 and result["no_amount"] * 2 >= total:
        proposal.status, proposal.outcome, proposal.decided_at = "rejected", "Voted down", now
        return
    if total <= 0 or result["yes_amount"] * 2 <= total:
        return

    fund = get_fund(db, proposal.fund_id, lock=True)
    price = Decimal(fund.share_price)
    amount = (price * proposal.shares).quantize(CENT)
    left = fund.total_shares - fund.shares_sold
    problem = None
    if not is_open(fund):
        problem = "The fund stopped selling shares before the vote passed"
    elif proposal.shares > left:
        problem = f"Only {left} shares were left when the vote passed"
    elif Decimal(circle.pool_balance) < amount:
        problem = f"The pool had {Decimal(circle.pool_balance):,.2f} but this costs {amount:,.2f}"
    if problem:
        proposal.status, proposal.outcome, proposal.decided_at = "failed", problem, now
        return

    circle.pool_balance = Decimal(circle.pool_balance) - amount
    fund.shares_sold += proposal.shares
    proposal.amount = amount
    proposal.status, proposal.outcome, proposal.decided_at = "passed", f"Bought {proposal.shares} shares", now
    db.add(CircleHolding(
        id=str(uuid.uuid4()), circle_id=circle.id, fund_id=fund.id, proposal_id=proposal.id,
        shares=proposal.shares, amount=amount,
    ))


def serialize_circle(db: Session, circle: InvestmentCircle, user_id: str, detail: bool = False) -> dict:
    members = db.query(CircleMember).filter_by(circle_id=circle.id).order_by(CircleMember.contributed.desc(), CircleMember.joined_at).all()
    total = Decimal(circle.total_contributed)
    mine = next((m for m in members if m.user_id == user_id), None)
    my_share = float(Decimal(mine.contributed) / total) if mine and total > 0 else 0.0
    holdings = db.query(CircleHolding).filter_by(circle_id=circle.id).all()
    invested = sum((Decimal(h.amount) for h in holdings), Decimal(0))

    users = {u.id: u for u in db.query(User).filter(User.id.in_([m.user_id for m in members]))} if members else {}
    data = {
        "id": circle.id,
        "name": circle.name,
        "purpose": circle.purpose,
        "min_contribution": money(circle.min_contribution),
        "pool_balance": money(circle.pool_balance),
        "total_contributed": money(total),
        "invested": money(invested),
        "member_count": len(members),
        "is_member": mine is not None,
        "is_creator": circle.creator_user_id == user_id,
        "my_contribution": money(mine.contributed) if mine else 0,
        "my_share": my_share,
        "open_proposals": db.query(CircleProposal).filter_by(circle_id=circle.id, status="open").count(),
        "created_at": circle.created_at.isoformat() + "Z",
        "members": [
            {
                "name": display_name(users.get(m.user_id)),
                "is_you": m.user_id == user_id,
                "contributed": money(m.contributed),
                "share": float(Decimal(m.contributed) / total) if total > 0 else 0.0,
            }
            for m in members
        ],
    }
    if not detail:
        return data

    funds = {f.id: f for f in db.query(VentureFund).filter(VentureFund.id.in_({h.fund_id for h in holdings} | {p.fund_id for p in db.query(CircleProposal).filter_by(circle_id=circle.id)}))}
    grouped: dict = {}
    for holding in holdings:
        entry = grouped.setdefault(holding.fund_id, {"shares": 0, "amount": Decimal(0)})
        entry["shares"] += holding.shares
        entry["amount"] += Decimal(holding.amount)
    data["holdings"] = [
        {
            "fund_id": fund_id,
            "fund_name": funds[fund_id].fund_name,
            "firm_name": funds[fund_id].firm_name,
            "shares": entry["shares"],
            "amount": money(entry["amount"]),
            "my_shares": round(entry["shares"] * my_share, 4),
            "my_value": money(entry["amount"] * Decimal(str(my_share))),
        }
        for fund_id, entry in grouped.items()
    ]
    proposals = db.query(CircleProposal).filter_by(circle_id=circle.id).order_by(CircleProposal.created_at.desc()).limit(50).all()
    rows = []
    for proposal in proposals:
        result = tally(db, proposal, total)
        voter_names = {"yes": [], "no": []}
        my_vote = None
        for vote in result["votes"]:
            voter_names[vote.choice].append(display_name(users.get(vote.user_id)) if vote.user_id != user_id else "You")
            if vote.user_id == user_id:
                my_vote = vote.choice
        fund = funds.get(proposal.fund_id)
        rows.append({
            "id": proposal.id,
            "fund_id": proposal.fund_id,
            "fund_name": fund.fund_name if fund else "Fund",
            "firm_name": fund.firm_name if fund else "",
            "shares": proposal.shares,
            "amount": money(proposal.amount),
            "note": proposal.note,
            "status": proposal.status,
            "outcome": proposal.outcome,
            "proposed_by": "You" if proposal.proposer_user_id == user_id else display_name(users.get(proposal.proposer_user_id)),
            "yes": result["yes"],
            "no": result["no"],
            "voters": voter_names,
            "my_vote": my_vote,
            "created_at": proposal.created_at.isoformat() + "Z",
        })
    data["proposals"] = rows
    data["cash_available"] = money(cash_balance(db, user_id))
    return data


@router.get("")
async def list_circles(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    circles = db.query(InvestmentCircle).order_by(InvestmentCircle.created_at.desc()).limit(200).all()
    rows = [serialize_circle(db, circle, user_id) for circle in circles]
    rows.sort(key=lambda row: not row["is_member"])
    return {"data": rows, "total": len(rows), "cash_available": money(cash_balance(db, user_id))}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_circle(payload: CircleCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    circle = InvestmentCircle(
        id=str(uuid.uuid4()), creator_user_id=user_id, name=payload.name.strip(), purpose=payload.purpose.strip(),
        min_contribution=payload.min_contribution, pool_balance=0, total_contributed=0,
    )
    db.add(circle)
    db.add(CircleMember(id=str(uuid.uuid4()), circle_id=circle.id, user_id=user_id, contributed=0))
    db.commit()
    return {"data": serialize_circle(db, circle, user_id, detail=True)}


@router.get("/{circle_id}")
async def circle_detail(circle_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return {"data": serialize_circle(db, get_circle(db, circle_id), user_id, detail=True)}


@router.post("/{circle_id}/join")
async def join_circle(circle_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    circle = get_circle(db, circle_id)
    if membership(db, circle_id, user_id) is None:
        db.add(CircleMember(id=str(uuid.uuid4()), circle_id=circle_id, user_id=user_id, contributed=0))
        db.commit()
    return {"data": serialize_circle(db, circle, user_id, detail=True)}


@router.post("/{circle_id}/contribute")
async def contribute(circle_id: str, payload: Contribution, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    circle = get_circle(db, circle_id, lock=True)
    member = require_member(db, circle_id, user_id)
    amount = payload.amount.quantize(CENT)
    if amount < Decimal(circle.min_contribution):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"The smallest contribution to this circle is ${Decimal(circle.min_contribution):,.2f}")
    account = (
        cash_accounts(db, user_id)
        .filter(Account.available_balance >= amount)
        .order_by(Account.is_primary.desc(), Account.available_balance.desc())
        .with_for_update()
        .first()
    )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Not enough cash. You're adding ${amount:,.2f} and your Hoardrun cash is ${cash_balance(db, user_id):,.2f}. Add money first.",
        )
    now = datetime.now(timezone.utc)
    account.available_balance = Decimal(account.available_balance) - amount
    account.current_balance = Decimal(account.current_balance) - amount
    db.add(Transaction(
        id=str(uuid.uuid4()), user_id=user_id, account_id=account.id,
        transaction_type=TransactionTypeEnum.INVESTMENT, status=TransactionStatusEnum.COMPLETED,
        direction=TransactionDirectionEnum.OUTBOUND, amount=amount, currency="USD",
        description=f"Added to {circle.name}", merchant_name="Hoardrun circle", payment_method=PaymentMethodEnum.OTHER,
        reference_number=f"IC-{uuid.uuid4().hex[:12].upper()}", transaction_date=now, posted_date=now,
        balance_after=account.current_balance,
    ))
    member.contributed = Decimal(member.contributed) + amount
    circle.pool_balance = Decimal(circle.pool_balance) + amount
    circle.total_contributed = Decimal(circle.total_contributed) + amount
    db.flush()
    # New money shifts everyone's weight, so open votes may now be decided
    for proposal in db.query(CircleProposal).filter_by(circle_id=circle_id, status="open").all():
        settle(db, circle, proposal)
    db.commit()
    return {"data": serialize_circle(db, circle, user_id, detail=True)}


@router.post("/{circle_id}/proposals", status_code=status.HTTP_201_CREATED)
async def propose(circle_id: str, payload: ProposalCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    circle = get_circle(db, circle_id, lock=True)
    member = require_member(db, circle_id, user_id)
    if Decimal(member.contributed) <= 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Add money to the circle before proposing an investment")
    fund = get_fund(db, payload.fund_id)
    if not is_open(fund):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That fund isn't selling shares any more")
    left = fund.total_shares - fund.shares_sold
    if payload.shares > left:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only {left} shares are left in that fund")
    if payload.shares < fund.min_shares:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"That fund's smallest purchase is {fund.min_shares} shares")
    amount = (Decimal(fund.share_price) * payload.shares).quantize(CENT)
    if amount > Decimal(circle.pool_balance):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"This costs ${amount:,.2f} but the pool has ${Decimal(circle.pool_balance):,.2f}")

    proposal = CircleProposal(
        id=str(uuid.uuid4()), circle_id=circle_id, proposer_user_id=user_id, fund_id=fund.id,
        shares=payload.shares, amount=amount, note=(payload.note or "").strip() or None, status="open",
    )
    db.add(proposal)
    db.add(CircleVote(id=str(uuid.uuid4()), proposal_id=proposal.id, user_id=user_id, choice="yes"))
    db.flush()
    settle(db, circle, proposal)
    db.commit()
    return {"data": serialize_circle(db, circle, user_id, detail=True)}


@router.post("/{circle_id}/proposals/{proposal_id}/vote")
async def vote(circle_id: str, proposal_id: str, payload: VoteCast, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    circle = get_circle(db, circle_id, lock=True)
    member = require_member(db, circle_id, user_id)
    if Decimal(member.contributed) <= 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only members who have added money can vote")
    proposal = db.query(CircleProposal).filter_by(id=proposal_id, circle_id=circle_id).with_for_update().first()
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    if proposal.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Voting on this proposal has closed")
    existing = db.query(CircleVote).filter_by(proposal_id=proposal_id, user_id=user_id).first()
    if existing:
        existing.choice = payload.choice
    else:
        db.add(CircleVote(id=str(uuid.uuid4()), proposal_id=proposal_id, user_id=user_id, choice=payload.choice))
    db.flush()
    settle(db, circle, proposal)
    db.commit()
    return {"data": serialize_circle(db, circle, user_id, detail=True)}
