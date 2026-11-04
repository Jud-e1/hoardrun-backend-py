"""
Monthly budgets, stored in the database.

A budget is a monthly limit for one spending category. What's been spent is never stored:
it's worked out from the user's own completed outgoing transactions this month, so it always
matches the transaction history.
"""

import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, DECIMAL, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...database.config import Base, get_db
from ...database.models import MerchantCategoryEnum as M, Transaction, TransactionDirectionEnum, TransactionStatusEnum
from ...services.inbox import notify

router = APIRouter(prefix="/budgets", tags=["budgets"])

CENT = Decimal("0.01")

# Each budget category covers these transaction categories. "other" covers anything uncategorised.
CATEGORIES: Dict[str, List[M]] = {
    "food": [M.GROCERIES, M.RESTAURANTS],
    "housing": [M.UTILITIES, M.HOME_IMPROVEMENT, M.INSURANCE],
    "transportation": [M.GAS_STATIONS, M.AUTOMOTIVE],
    "entertainment": [M.ENTERTAINMENT, M.SUBSCRIPTION, M.ONLINE_SERVICES],
    "shopping": [M.RETAIL],
    "healthcare": [M.HEALTHCARE],
    "education": [M.EDUCATION],
    "travel": [M.TRAVEL],
    "transfers": [M.TRANSFER],
    "other": [M.OTHER, M.PROFESSIONAL_SERVICES, M.GOVERNMENT, M.CHARITY, M.ATM_FEE, M.BANK_FEE, M.CASH_ADVANCE],
}
# Money moved into the user's own savings isn't spending
INTERNAL_MERCHANTS = {"Hoardrun Savings"}


class Budget(Base):
    __tablename__ = "budgets_store"
    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_budget_category"),)

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(60), nullable=False)
    category = Column(String(20), nullable=False)
    monthly_limit = Column(DECIMAL(18, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class BudgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    category: str = Field(default="other")
    budgeted_amount: Decimal = Field(gt=0, le=Decimal("1000000"), decimal_places=2)


class BudgetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    budgeted_amount: Optional[Decimal] = Field(default=None, gt=0, le=Decimal("1000000"), decimal_places=2)


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1)


def shift_month(year: int, month: int, delta: int):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def spending(db: Session, user_id: str, start: datetime, end: datetime) -> Dict[str, Decimal]:
    """Spent per budget category between two dates, from completed outgoing transactions."""
    rows = (
        db.query(Transaction.merchant_category, Transaction.amount, Transaction.merchant_name)
        .filter(
            Transaction.user_id == user_id,
            Transaction.direction == TransactionDirectionEnum.OUTBOUND,
            Transaction.status == TransactionStatusEnum.COMPLETED,
            Transaction.created_at >= start,
            Transaction.created_at < end,
        )
        .all()
    )
    lookup = {merchant: key for key, merchants in CATEGORIES.items() for merchant in merchants}
    totals: Dict[str, Decimal] = {key: Decimal(0) for key in CATEGORIES}
    for category, amount, merchant in rows:
        if merchant in INTERNAL_MERCHANTS or category == M.INVESTMENT_TRADE:
            continue
        totals[lookup.get(category, "other")] += Decimal(str(amount))
    return totals


def this_month(db: Session, user_id: str) -> Dict[str, Decimal]:
    now = datetime.utcnow()
    year, month = shift_month(now.year, now.month, 1)
    return spending(db, user_id, month_start(now.year, now.month), month_start(year, month))


def check_alerts(db: Session, user_id: str) -> None:
    """Notify when a budget passes 80% or 100% of its limit this month."""
    spent = this_month(db, user_id)
    month = datetime.utcnow().strftime("%Y-%m")
    changed = False
    for budget in db.query(Budget).filter(Budget.user_id == user_id).all():
        limit = Decimal(budget.monthly_limit)
        used = spent.get(budget.category, Decimal(0))
        if not limit:
            continue
        if used > limit:
            changed |= notify(db, user_id, "warning", f"Over your {budget.name} budget",
                              f"You've spent ${used:,.2f} of ${limit:,.2f} this month.", link="/budget",
                              key=f"budget-over:{budget.id}:{month}", email=True) is not None
        elif used >= limit * Decimal("0.8"):
            changed |= notify(db, user_id, "info", f"{budget.name} budget is {used / limit:.0%} used",
                              f"${limit - used:,.2f} left for the rest of the month.", link="/budget",
                              key=f"budget-80:{budget.id}:{month}") is not None
    if changed:
        db.commit()


def budget_out(budget: Budget, spent: Decimal) -> dict:
    limit = Decimal(budget.monthly_limit)
    return {
        "id": budget.id,
        "name": budget.name,
        "category": budget.category,
        "budgeted_amount": float(limit),
        "spent_amount": float(money(spent)),
        "remaining": float(money(limit - spent)),
        "percentage_used": float(round(spent / limit * 100, 1)) if limit else 0.0,
    }


def own_budget(db: Session, user_id: str, budget_id: str) -> Budget:
    budget = db.query(Budget).filter(Budget.id == budget_id, Budget.user_id == user_id).first()
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


@router.get("/categories")
async def categories():
    return [{"key": key, "covers": [m.value for m in merchants]} for key, merchants in CATEGORIES.items()]


@router.get("")
async def list_budgets(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    check_alerts(db, user_id)
    spent = this_month(db, user_id)
    budgets = db.query(Budget).filter(Budget.user_id == user_id).order_by(Budget.created_at).all()
    return [budget_out(b, spent.get(b.category, Decimal(0))) for b in budgets]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_budget(payload: BudgetCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    category = payload.category.lower().strip()
    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Pick one of: {', '.join(CATEGORIES)}.")
    if db.query(Budget).filter(Budget.user_id == user_id, Budget.category == category).first():
        raise HTTPException(status_code=409, detail=f"You already have a {category} budget. Edit it instead.")
    budget = Budget(id=str(uuid.uuid4()), user_id=user_id, name=payload.name.strip(), category=category,
                    monthly_limit=money(payload.budgeted_amount))
    db.add(budget)
    db.commit()
    return budget_out(budget, this_month(db, user_id).get(category, Decimal(0)))


@router.patch("/{budget_id}")
async def update_budget(budget_id: str, payload: BudgetUpdate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    budget = own_budget(db, user_id, budget_id)
    if payload.name is not None:
        budget.name = payload.name.strip()
    if payload.budgeted_amount is not None:
        budget.monthly_limit = money(payload.budgeted_amount)
    db.commit()
    return budget_out(budget, this_month(db, user_id).get(budget.category, Decimal(0)))


@router.delete("/{budget_id}")
async def delete_budget(budget_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    db.delete(own_budget(db, user_id, budget_id))
    db.commit()
    return {"deleted": True}


@router.get("/summary")
async def summary(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    spent = this_month(db, user_id)
    budgets = db.query(Budget).filter(Budget.user_id == user_id).all()
    total_limit = sum((Decimal(b.monthly_limit) for b in budgets), Decimal(0))
    total_spent = sum((spent.get(b.category, Decimal(0)) for b in budgets), Decimal(0))
    return {
        "total_budgeted": float(money(total_limit)),
        "total_spent": float(money(total_spent)),
        "total_remaining": float(money(total_limit - total_spent)),
        "overall_percentage_used": float(round(total_spent / total_limit * 100, 1)) if total_limit else 0.0,
        "unbudgeted_spending": float(money(sum((v for k, v in spent.items() if k not in {b.category for b in budgets}), Decimal(0)))),
    }


@router.get("/trend")
async def trend(months: int = Query(6, ge=1, le=12), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Spent in budgeted categories for each of the last few months, against today's limits."""
    budgets = db.query(Budget).filter(Budget.user_id == user_id).all()
    covered = {b.category for b in budgets}
    limit = float(money(sum((Decimal(b.monthly_limit) for b in budgets), Decimal(0))))
    now = datetime.utcnow()
    points = []
    for back in range(months - 1, -1, -1):
        year, month = shift_month(now.year, now.month, -back)
        next_year, next_month = shift_month(year, month, 1)
        spent = spending(db, user_id, month_start(year, month), month_start(next_year, next_month))
        points.append({
            "month": month_start(year, month).strftime("%b"),
            "budgeted": limit,
            "spent": float(money(sum((v for k, v in spent.items() if k in covered), Decimal(0)))),
        })
    return points
