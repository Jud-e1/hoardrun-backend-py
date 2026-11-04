"""
Venture capital: firms register funds, people buy shares in them with Hoardrun cash.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...database.config import get_db
from ...database.models import (
    Account, AccountStatusEnum, PaymentMethodEnum, Transaction, TransactionDirectionEnum,
    TransactionStatusEnum, TransactionTypeEnum,
)
from ...database.venture_models import FundShareOrder, VentureFund

router = APIRouter(prefix="/venture-funds", tags=["venture-funds"])

Stage = Literal["pre-seed", "seed", "series-a", "growth"]


class VentureFundCreate(BaseModel):
    firm_name: str = Field(min_length=2, max_length=80)
    fund_name: str = Field(min_length=2, max_length=80)
    thesis: str = Field(min_length=10, max_length=160)
    about: Optional[str] = Field(default=None, max_length=4000)
    sectors: List[str] = Field(min_length=1, max_length=3)
    stage: Stage
    location: Optional[str] = Field(default=None, max_length=80)
    website: Optional[str] = Field(default=None, max_length=200)
    share_price: Decimal = Field(ge=Decimal("1"), le=Decimal("1000000"), decimal_places=2)
    total_shares: int = Field(ge=10, le=10_000_000)
    min_shares: int = Field(default=1, ge=1)
    term_years: int = Field(ge=1, le=15)
    management_fee: Decimal = Field(ge=0, le=5)
    carry: Decimal = Field(ge=0, le=40)
    closes_on: Optional[date] = None

    @field_validator("firm_name", "fund_name", "thesis", "about", "location", "website", mode="before")
    @classmethod
    def strip_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("sectors")
    @classmethod
    def clean_sectors(cls, value):
        cleaned = list(dict.fromkeys(item.strip()[:30] for item in value if item and item.strip()))
        if not cleaned:
            raise ValueError("Pick at least one sector")
        return cleaned

    @field_validator("website")
    @classmethod
    def check_website(cls, value):
        if value and not value.lower().startswith(("https://", "http://")):
            value = f"https://{value}"
        return value

    @field_validator("closes_on")
    @classmethod
    def check_closing(cls, value):
        if value is not None and value <= date.today():
            raise ValueError("The closing date has to be in the future")
        return value

    @model_validator(mode="after")
    def check_minimum(self):
        if self.min_shares > self.total_shares:
            raise ValueError("The minimum purchase can't be more than the whole fund")
        return self


class BuyShares(BaseModel):
    shares: int = Field(ge=1, le=10_000_000)


def cash_accounts(db: Session, user_id: str):
    return db.query(Account).filter(
        Account.user_id == user_id,
        Account.currency == "USD",
        Account.status == AccountStatusEnum.ACTIVE,
    )


def cash_balance(db: Session, user_id: str) -> Decimal:
    total = cash_accounts(db, user_id).with_entities(func.coalesce(func.sum(Account.available_balance), 0)).scalar()
    return Decimal(str(total or 0))


def is_open(fund: VentureFund) -> bool:
    return fund.shares_sold < fund.total_shares and (fund.closes_on is None or fund.closes_on >= date.today())


def serialize(fund: VentureFund, user_id: str, owned: int = 0) -> dict:
    price = Decimal(fund.share_price)
    return {
        "id": fund.id,
        "firm_name": fund.firm_name,
        "fund_name": fund.fund_name,
        "thesis": fund.thesis,
        "about": fund.about,
        "sectors": fund.sectors or [],
        "stage": fund.stage,
        "location": fund.location,
        "website": fund.website,
        "share_price": float(price),
        "total_shares": fund.total_shares,
        "min_shares": fund.min_shares,
        "shares_sold": fund.shares_sold,
        "shares_left": fund.total_shares - fund.shares_sold,
        "target_size": float(price * fund.total_shares),
        "amount_raised": float(price * fund.shares_sold),
        "term_years": fund.term_years,
        "management_fee": float(fund.management_fee),
        "carry": float(fund.carry),
        "closes_on": fund.closes_on.isoformat() if fund.closes_on else None,
        "is_open": is_open(fund),
        "created_at": fund.created_at.isoformat() + "Z",
        "is_manager": fund.manager_user_id == user_id,
        "my_shares": owned,
    }


def owned_shares(db: Session, user_id: str) -> dict:
    rows = (
        db.query(FundShareOrder.fund_id, func.sum(FundShareOrder.shares))
        .filter(FundShareOrder.user_id == user_id)
        .group_by(FundShareOrder.fund_id)
        .all()
    )
    return {fund_id: int(total or 0) for fund_id, total in rows}


def get_fund(db: Session, fund_id: str, lock: bool = False) -> VentureFund:
    query = db.query(VentureFund).filter(VentureFund.id == fund_id)
    if lock:
        query = query.with_for_update()
    fund = query.first()
    if fund is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found")
    return fund


@router.get("")
async def list_funds(
    q: Optional[str] = Query(default=None, max_length=80),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    query = db.query(VentureFund)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(VentureFund.fund_name.ilike(term), VentureFund.firm_name.ilike(term), VentureFund.thesis.ilike(term)))
    funds = query.order_by(VentureFund.created_at.desc()).limit(200).all()
    owned = owned_shares(db, user_id)
    return {
        "data": [serialize(fund, user_id, owned.get(fund.id, 0)) for fund in funds],
        "total": len(funds),
        "cash_available": float(cash_balance(db, user_id)),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_fund(payload: VentureFundCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    fund = VentureFund(id=str(uuid.uuid4()), manager_user_id=user_id, shares_sold=0, **payload.model_dump())
    db.add(fund)
    db.commit()
    db.refresh(fund)
    return {"data": serialize(fund, user_id)}


@router.get("/holdings")
async def holdings(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    owned = owned_shares(db, user_id)
    funds = db.query(VentureFund).filter(VentureFund.id.in_(list(owned))).all() if owned else []
    rows = [serialize(fund, user_id, owned[fund.id]) for fund in funds]
    return {"data": rows, "total_value": sum(row["share_price"] * row["my_shares"] for row in rows)}


@router.get("/{fund_id}")
async def fund_detail(fund_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    fund = get_fund(db, fund_id)
    return {"data": serialize(fund, user_id, owned_shares(db, user_id).get(fund.id, 0)), "cash_available": float(cash_balance(db, user_id))}


@router.post("/{fund_id}/buy", status_code=status.HTTP_201_CREATED)
async def buy_shares(fund_id: str, payload: BuyShares, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    fund = get_fund(db, fund_id, lock=True)
    if fund.manager_user_id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You can't buy shares in a fund you manage")
    if not is_open(fund):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This fund isn't selling shares any more")
    left = fund.total_shares - fund.shares_sold
    if payload.shares > left:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only {left} shares are left in this fund")
    if payload.shares < fund.min_shares:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"The smallest purchase is {fund.min_shares} shares")

    price = Decimal(fund.share_price)
    amount = (price * payload.shares).quantize(Decimal("0.01"))
    account = (
        cash_accounts(db, user_id)
        .filter(Account.available_balance >= amount)
        .order_by(Account.is_primary.desc(), Account.available_balance.desc())
        .with_for_update()
        .first()
    )
    if account is None:
        have = cash_balance(db, user_id)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Not enough cash. {payload.shares} shares cost ${amount:,.2f} and your Hoardrun cash is ${have:,.2f}. Add money first.",
        )

    now = datetime.now(timezone.utc)
    account.available_balance = Decimal(account.available_balance) - amount
    account.current_balance = Decimal(account.current_balance) - amount
    transaction = Transaction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        account_id=account.id,
        transaction_type=TransactionTypeEnum.INVESTMENT,
        status=TransactionStatusEnum.COMPLETED,
        direction=TransactionDirectionEnum.OUTBOUND,
        amount=amount,
        currency="USD",
        description=f"{payload.shares} shares of {fund.fund_name}",
        merchant_name=fund.firm_name,
        payment_method=PaymentMethodEnum.OTHER,
        reference_number=f"VF-{uuid.uuid4().hex[:12].upper()}",
        transaction_date=now,
        posted_date=now,
        balance_after=account.current_balance,
    )
    order = FundShareOrder(
        id=str(uuid.uuid4()), fund_id=fund.id, user_id=user_id, account_id=account.id,
        transaction_id=transaction.id, shares=payload.shares, share_price=price, amount=amount,
    )
    fund.shares_sold += payload.shares
    db.add_all([transaction, order])
    db.commit()

    return {
        "data": {
            "order_id": order.id,
            "reference": transaction.reference_number,
            "shares": payload.shares,
            "amount": float(amount),
            "purchased_at": now.isoformat(),
            "fund": serialize(fund, user_id, owned_shares(db, user_id).get(fund.id, 0)),
            "cash_available": float(cash_balance(db, user_id)),
        }
    }


@router.delete("/{fund_id}")
async def delete_fund(fund_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    fund = get_fund(db, fund_id)
    if fund.manager_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the fund's manager can remove it")
    if fund.shares_sold > 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="People already hold shares in this fund, so it can't be removed")
    db.delete(fund)
    db.commit()
    return {"data": {"id": fund_id, "deleted": True}}
