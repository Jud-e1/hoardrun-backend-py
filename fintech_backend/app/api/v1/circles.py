"""
Investment circles: a group decides together what to invest in.

- Joining: anyone can ask to join; the circle's admin (its creator) accepts or declines.
  A circle can set how many people it takes.
- Proposals: a member proposes an investment, either a type of asset (private equity,
  real estate, ETFs...) with an amount each person puts in, or venture fund shares bought
  from the circle's pooled cash.
- Voting: one person, one vote. A proposal goes ahead only when MORE than half of the
  members vote yes and at least two people agree, so one person can never decide alone.
  It is turned down once half or more vote no, since a majority is then impossible.
- Money: for an asset proposal, only the people who voted yes pay, and their share is
  taken from their Hoardrun cash the moment the vote passes. Fund proposals spend the pool.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...database.circle_models import (
    CircleHolding, CircleInvestment, CircleMember, CircleProposal, CircleVote, InvestmentCircle,
)
from ...database.config import get_db
from ...database.models import (
    Account, PaymentMethodEnum, Transaction, TransactionDirectionEnum, TransactionStatusEnum,
    TransactionTypeEnum, User,
)
from ...database.venture_models import VentureFund
from .venture import cash_accounts, cash_balance, get_fund, is_open

router = APIRouter(prefix="/circles", tags=["circles"])

CENT = Decimal("0.01")
ACTIVE, PENDING = "active", "pending"

# What a circle can invest in together
ASSET_TYPES = {
    "private_equity": "Private equity",
    "real_estate": "Real estate",
    "fixed_income": "Fixed income",
    "etfs": "ETFs",
    "stocks": "Stocks",
    "crypto": "Crypto",
    "startups": "Startups",
    "venture_fund": "Venture fund",
    "other": "Other",
}
AssetType = Literal["private_equity", "real_estate", "fixed_income", "etfs", "stocks", "crypto", "startups", "venture_fund", "other"]


class CircleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    purpose: str = Field(min_length=10, max_length=160)
    min_contribution: Decimal = Field(default=Decimal("10"), ge=Decimal("1"), le=Decimal("1000000"), decimal_places=2)
    focus: Optional[AssetType] = None
    max_members: Optional[int] = Field(default=None, ge=2, le=500)


class JoinRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=200)


class Contribution(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("10000000"), decimal_places=2)


class ProposalCreate(BaseModel):
    kind: Literal["asset", "fund"] = "fund"
    # kind "asset"
    asset_type: Optional[AssetType] = None
    title: Optional[str] = Field(default=None, min_length=3, max_length=80)
    amount_per_member: Optional[Decimal] = Field(default=None, ge=Decimal("1"), le=Decimal("1000000"), decimal_places=2)
    # kind "fund"
    fund_id: Optional[str] = None
    shares: Optional[int] = Field(default=None, ge=1, le=10_000_000)
    note: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def complete(self):
        if self.kind == "asset" and (self.asset_type is None or not self.title or self.amount_per_member is None):
            raise ValueError("Choose the type of investment, give it a name and say how much each person puts in")
        if self.kind == "fund" and (not self.fund_id or self.shares is None):
            raise ValueError("Choose a fund and how many shares to buy")
        return self


class VoteCast(BaseModel):
    choice: Literal["yes", "no"]


def money(value) -> float:
    return float(Decimal(value or 0).quantize(CENT))


def iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() + "Z" if value else None


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


def active_members(db: Session, circle_id: str) -> List[CircleMember]:
    return db.query(CircleMember).filter_by(circle_id=circle_id, status=ACTIVE).all()


def require_member(db: Session, circle_id: str, user_id: str) -> CircleMember:
    member = membership(db, circle_id, user_id)
    if member is None or member.status != ACTIVE:
        detail = "The admin hasn't accepted your request yet" if member else "Join the circle first"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return member


def require_admin(circle: InvestmentCircle, user_id: str) -> None:
    if circle.creator_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the circle's admin can do that")


def needed_yes(member_count: int) -> int:
    """Yes votes needed: more than half the members, and never fewer than two people."""
    return max(member_count // 2 + 1, 2)


def tally(db: Session, proposal: CircleProposal, member_ids: set) -> dict:
    yes, no = [], []
    for vote in db.query(CircleVote).filter_by(proposal_id=proposal.id):
        if vote.user_id in member_ids:
            (yes if vote.choice == "yes" else no).append(vote.user_id)
    return {"yes": yes, "no": no}


def take_cash(db: Session, user_id: str, amount: Decimal, description: str) -> bool:
    """Move amount out of the member's Hoardrun cash with a ledger entry. False if they don't have it."""
    account = (
        cash_accounts(db, user_id)
        .filter(Account.available_balance >= amount)
        .order_by(Account.is_primary.desc(), Account.available_balance.desc())
        .with_for_update()
        .first()
    )
    if account is None:
        return False
    now = datetime.now(timezone.utc)
    account.available_balance = Decimal(account.available_balance) - amount
    account.current_balance = Decimal(account.current_balance) - amount
    db.add(Transaction(
        id=str(uuid.uuid4()), user_id=user_id, account_id=account.id,
        transaction_type=TransactionTypeEnum.INVESTMENT, status=TransactionStatusEnum.COMPLETED,
        direction=TransactionDirectionEnum.OUTBOUND, amount=amount, currency="USD",
        description=description, merchant_name="Hoardrun circle", payment_method=PaymentMethodEnum.OTHER,
        reference_number=f"IC-{uuid.uuid4().hex[:12].upper()}", transaction_date=now, posted_date=now,
        balance_after=account.current_balance,
    ))
    return True


def settle(db: Session, circle: InvestmentCircle, proposal: CircleProposal) -> None:
    """Go ahead with or turn down an open proposal once the members' votes decide it."""
    if proposal.status != "open":
        return
    members = {m.user_id for m in active_members(db, circle.id)}
    count = len(members)
    result = tally(db, proposal, members)
    now = datetime.now(timezone.utc)
    if count and len(result["no"]) * 2 >= count:
        proposal.status, proposal.outcome, proposal.decided_at = "rejected", "Voted down: a majority can't say yes", now
        return
    if len(result["yes"]) < needed_yes(count):
        return

    if proposal.kind == "asset":
        each = Decimal(proposal.amount_per_member).quantize(CENT)
        label = ASSET_TYPES.get(proposal.asset_type or "", "investment")
        # Check first, so nobody is charged unless at least two of the people who agreed can pay
        can_pay = [uid for uid in result["yes"] if cash_balance(db, uid) >= each]
        if len(can_pay) < 2:
            proposal.status, proposal.decided_at = "failed", now
            proposal.outcome = f"Passed, but fewer than 2 of the people who agreed had ${each:,.2f} in cash"
            return
        paid = [uid for uid in can_pay if take_cash(db, uid, each, f"{circle.name}: {proposal.title}")]
        for uid in paid:
            db.add(CircleInvestment(id=str(uuid.uuid4()), circle_id=circle.id, proposal_id=proposal.id, user_id=uid, amount=each))
        skipped = len(result["yes"]) - len(paid)
        proposal.amount = (each * len(paid)).quantize(CENT)
        proposal.status, proposal.decided_at = "passed", now
        proposal.outcome = f"Invested ${proposal.amount:,.2f} in {label.lower()} from {len(paid)} people" + (
            f"; {skipped} didn't have enough cash" if skipped else ""
        )
        return

    fund = get_fund(db, proposal.fund_id, lock=True)
    amount = (Decimal(fund.share_price) * proposal.shares).quantize(CENT)
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


def settle_open(db: Session, circle: InvestmentCircle) -> None:
    """Membership changed: open votes may now be decided (the majority moved)."""
    for proposal in db.query(CircleProposal).filter_by(circle_id=circle.id, status="open").all():
        settle(db, circle, proposal)


def serialize_circle(db: Session, circle: InvestmentCircle, user_id: str, detail: bool = False) -> dict:
    everyone = db.query(CircleMember).filter_by(circle_id=circle.id).order_by(CircleMember.contributed.desc(), CircleMember.joined_at).all()
    members = [m for m in everyone if m.status == ACTIVE]
    pending = [m for m in everyone if m.status == PENDING]
    total = Decimal(circle.total_contributed)
    mine = next((m for m in everyone if m.user_id == user_id), None)
    is_member = mine is not None and mine.status == ACTIVE
    is_admin = circle.creator_user_id == user_id
    my_share = float(Decimal(mine.contributed) / total) if is_member and total > 0 else 0.0
    holdings = db.query(CircleHolding).filter_by(circle_id=circle.id).all()
    investments = db.query(CircleInvestment).filter_by(circle_id=circle.id).all()
    invested = sum((Decimal(h.amount) for h in holdings), Decimal(0)) + sum((Decimal(i.amount) for i in investments), Decimal(0))
    my_invested = sum((Decimal(i.amount) for i in investments if i.user_id == user_id), Decimal(0))

    users = {u.id: u for u in db.query(User).filter(User.id.in_([m.user_id for m in everyone]))} if everyone else {}
    invested_by = {}
    for item in investments:
        invested_by[item.user_id] = invested_by.get(item.user_id, Decimal(0)) + Decimal(item.amount)
    data = {
        "id": circle.id,
        "name": circle.name,
        "purpose": circle.purpose,
        "focus": circle.focus,
        "focus_label": ASSET_TYPES.get(circle.focus) if circle.focus else None,
        "max_members": circle.max_members,
        "is_full": bool(circle.max_members and len(members) >= circle.max_members),
        "min_contribution": money(circle.min_contribution),
        "pool_balance": money(circle.pool_balance),
        "total_contributed": money(total),
        "invested": money(invested),
        "member_count": len(members),
        "votes_needed": needed_yes(len(members)),
        "my_status": "member" if is_member else ("pending" if mine else None),
        "is_member": is_member,
        "is_creator": is_admin,
        "is_admin": is_admin,
        "pending_count": len(pending) if is_admin else 0,
        "my_contribution": money(mine.contributed) if is_member else 0,
        "my_share": my_share,
        "my_invested": money(my_invested),
        "open_proposals": db.query(CircleProposal).filter_by(circle_id=circle.id, status="open").count(),
        "created_at": iso(circle.created_at),
        "members": [
            {
                "name": display_name(users.get(m.user_id)),
                "is_you": m.user_id == user_id,
                "is_admin": m.user_id == circle.creator_user_id,
                "contributed": money(m.contributed),
                "invested": money(invested_by.get(m.user_id, 0)),
                "share": float(Decimal(m.contributed) / total) if total > 0 else 0.0,
            }
            for m in members
        ],
    }
    if not detail:
        return data

    data["asset_types"] = [{"value": key, "label": label} for key, label in ASSET_TYPES.items()]
    data["requests"] = [
        {"id": m.id, "name": display_name(users.get(m.user_id)), "note": m.requested_note, "requested_at": iso(m.joined_at)}
        for m in pending
    ] if is_admin else []

    proposals = db.query(CircleProposal).filter_by(circle_id=circle.id).order_by(CircleProposal.created_at.desc()).limit(50).all()
    fund_ids = {h.fund_id for h in holdings} | {p.fund_id for p in proposals if p.fund_id}
    funds = {f.id: f for f in db.query(VentureFund).filter(VentureFund.id.in_(fund_ids))} if fund_ids else {}
    grouped: dict = {}
    for holding in holdings:
        entry = grouped.setdefault(holding.fund_id, {"shares": 0, "amount": Decimal(0)})
        entry["shares"] += holding.shares
        entry["amount"] += Decimal(holding.amount)
    data["holdings"] = [
        {
            "fund_id": fund_id,
            "fund_name": funds[fund_id].fund_name if fund_id in funds else "Fund",
            "firm_name": funds[fund_id].firm_name if fund_id in funds else "",
            "shares": entry["shares"],
            "amount": money(entry["amount"]),
            "my_shares": round(entry["shares"] * my_share, 4),
            "my_value": money(entry["amount"] * Decimal(str(my_share))),
        }
        for fund_id, entry in grouped.items()
    ]

    member_ids = {m.user_id for m in members}
    rows = []
    for proposal in proposals:
        result = tally(db, proposal, member_ids)
        voters = {
            choice: ["You" if uid == user_id else display_name(users.get(uid)) for uid in result[choice]]
            for choice in ("yes", "no")
        }
        my_vote = "yes" if user_id in result["yes"] else "no" if user_id in result["no"] else None
        fund = funds.get(proposal.fund_id) if proposal.fund_id else None
        is_asset = proposal.kind == "asset"
        count = len(members)
        rows.append({
            "id": proposal.id,
            "kind": proposal.kind,
            "asset_type": proposal.asset_type if is_asset else "venture_fund",
            "asset_label": ASSET_TYPES.get(proposal.asset_type or "", "Investment") if is_asset else "Venture fund",
            "title": proposal.title if is_asset else (fund.fund_name if fund else "Fund"),
            "amount_per_member": money(proposal.amount_per_member) if is_asset else None,
            "fund_id": proposal.fund_id,
            "fund_name": fund.fund_name if fund else None,
            "firm_name": fund.firm_name if fund else "",
            "shares": proposal.shares,
            "amount": money(proposal.amount),
            "note": proposal.note,
            "status": proposal.status,
            "outcome": proposal.outcome,
            "proposed_by": "You" if proposal.proposer_user_id == user_id else display_name(users.get(proposal.proposer_user_id)),
            "yes_count": len(result["yes"]),
            "no_count": len(result["no"]),
            "member_count": count,
            "votes_needed": needed_yes(count),
            "yes": len(result["yes"]) / count if count else 0.0,
            "no": len(result["no"]) / count if count else 0.0,
            "voters": voters,
            "my_vote": my_vote,
            "my_paid": money(sum((Decimal(i.amount) for i in investments if i.proposal_id == proposal.id and i.user_id == user_id), Decimal(0))),
            "created_at": iso(proposal.created_at),
            "decided_at": iso(proposal.decided_at),
        })
    data["proposals"] = rows
    data["cash_available"] = money(cash_balance(db, user_id))
    return data


@router.get("")
async def list_circles(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    circles = db.query(InvestmentCircle).order_by(InvestmentCircle.created_at.desc()).limit(200).all()
    rows = [serialize_circle(db, circle, user_id) for circle in circles]
    order = {"member": 0, "pending": 1, None: 2}
    rows.sort(key=lambda row: order[row["my_status"]])
    return {"data": rows, "total": len(rows), "cash_available": money(cash_balance(db, user_id)),
            "asset_types": [{"value": key, "label": label} for key, label in ASSET_TYPES.items()]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_circle(payload: CircleCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    circle = InvestmentCircle(
        id=str(uuid.uuid4()), creator_user_id=user_id, name=payload.name.strip(), purpose=payload.purpose.strip(),
        min_contribution=payload.min_contribution, pool_balance=0, total_contributed=0,
        focus=payload.focus, max_members=payload.max_members,
    )
    db.add(circle)
    db.add(CircleMember(id=str(uuid.uuid4()), circle_id=circle.id, user_id=user_id, contributed=0, status=ACTIVE))
    db.commit()
    return {"data": serialize_circle(db, circle, user_id, detail=True)}


@router.get("/{circle_id}")
async def circle_detail(circle_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return {"data": serialize_circle(db, get_circle(db, circle_id), user_id, detail=True)}


@router.post("/{circle_id}/join")
async def join_circle(circle_id: str, payload: Optional[JoinRequest] = Body(default=None),
                      user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Ask to join. The admin accepts or declines; until then you're on the waiting list."""
    circle = get_circle(db, circle_id, lock=True)
    if membership(db, circle_id, user_id) is None:
        if circle.max_members and len(active_members(db, circle_id)) >= circle.max_members:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This circle is full")
        is_admin = circle.creator_user_id == user_id
        note = ((payload.note or "").strip() or None) if payload else None
        db.add(CircleMember(id=str(uuid.uuid4()), circle_id=circle_id, user_id=user_id, contributed=0,
                            status=ACTIVE if is_admin else PENDING, requested_note=note))
        db.commit()
    return {"data": serialize_circle(db, circle, user_id, detail=True)}


@router.delete("/{circle_id}/join")
async def cancel_request(circle_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Withdraw a request the admin hasn't answered yet."""
    circle = get_circle(db, circle_id)
    member = membership(db, circle_id, user_id)
    if member is not None and member.status == PENDING:
        db.delete(member)
        db.commit()
    return {"data": serialize_circle(db, circle, user_id, detail=True)}


@router.post("/{circle_id}/requests/{member_id}/{decision}")
async def answer_request(circle_id: str, member_id: str, decision: Literal["approve", "decline"],
                         user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """The admin accepts or declines someone who asked to join."""
    circle = get_circle(db, circle_id, lock=True)
    require_admin(circle, user_id)
    member = db.query(CircleMember).filter_by(id=member_id, circle_id=circle_id, status=PENDING).with_for_update().first()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="That request was already answered")
    if decision == "decline":
        db.delete(member)
    else:
        if circle.max_members and len(active_members(db, circle_id)) >= circle.max_members:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The circle is full. Raise its size to accept more people")
        member.status = ACTIVE
        member.joined_at = datetime.utcnow()
        db.flush()
        settle_open(db, circle)
    db.commit()
    return {"data": serialize_circle(db, circle, user_id, detail=True)}


@router.post("/{circle_id}/contribute")
async def contribute(circle_id: str, payload: Contribution, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    circle = get_circle(db, circle_id, lock=True)
    member = require_member(db, circle_id, user_id)
    amount = payload.amount.quantize(CENT)
    if amount < Decimal(circle.min_contribution):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"The smallest contribution to this circle is ${Decimal(circle.min_contribution):,.2f}")
    if not take_cash(db, user_id, amount, f"Added to {circle.name}"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Not enough cash. You're adding ${amount:,.2f} and your Hoardrun cash is ${cash_balance(db, user_id):,.2f}. Add money first.",
        )
    member.contributed = Decimal(member.contributed) + amount
    circle.pool_balance = Decimal(circle.pool_balance) + amount
    circle.total_contributed = Decimal(circle.total_contributed) + amount
    db.flush()
    # More money in the pool may let a passed fund proposal go ahead
    settle_open(db, circle)
    db.commit()
    return {"data": serialize_circle(db, circle, user_id, detail=True)}


@router.post("/{circle_id}/proposals", status_code=status.HTTP_201_CREATED)
async def propose(circle_id: str, payload: ProposalCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    circle = get_circle(db, circle_id, lock=True)
    member = require_member(db, circle_id, user_id)
    note = (payload.note or "").strip() or None

    if payload.kind == "asset":
        each = payload.amount_per_member.quantize(CENT)
        if cash_balance(db, user_id) < each:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                                detail=f"You'd put in ${each:,.2f} too, but your Hoardrun cash is ${cash_balance(db, user_id):,.2f}. Add money first.")
        proposal = CircleProposal(
            id=str(uuid.uuid4()), circle_id=circle_id, proposer_user_id=user_id, kind="asset",
            asset_type=payload.asset_type, title=payload.title.strip(), amount_per_member=each,
            amount=Decimal(0), note=note, status="open",
        )
    else:
        if Decimal(member.contributed) <= 0:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Add money to the circle's pool before proposing a fund purchase")
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
            id=str(uuid.uuid4()), circle_id=circle_id, proposer_user_id=user_id, kind="fund", fund_id=fund.id,
            shares=payload.shares, amount=amount, note=note, status="open",
        )

    db.add(proposal)
    # Proposing counts as agreeing
    db.add(CircleVote(id=str(uuid.uuid4()), proposal_id=proposal.id, user_id=user_id, choice="yes"))
    db.flush()
    settle(db, circle, proposal)
    db.commit()
    return {"data": serialize_circle(db, circle, user_id, detail=True)}


@router.post("/{circle_id}/proposals/{proposal_id}/vote")
async def vote(circle_id: str, proposal_id: str, payload: VoteCast, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    circle = get_circle(db, circle_id, lock=True)
    require_member(db, circle_id, user_id)
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
