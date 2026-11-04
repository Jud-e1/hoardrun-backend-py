"""
Savings, stored for real: goals, fixed deposits and auto-save plans.

Money moves between the user's Hoardrun cash and their savings, and every move is a ledger
transaction on the cash account, so balances, history and exports all agree.
Auto-save plans run when they fall due; due runs are caught up whenever savings are read.
"""

import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, Date, DateTime, DECIMAL, ForeignKey, Integer, String
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...database.config import Base, get_db
from ...database.models import (
    Account, PaymentMethodEnum, Transaction, TransactionDirectionEnum, TransactionStatusEnum, TransactionTypeEnum,
)
from ...services.deposit_ledger import cash_account
from ...services.inbox import notify
from .venture import cash_accounts, cash_balance

router = APIRouter(prefix="/savings", tags=["savings"])

CENT = Decimal("0.01")
MAX_MOVE = Decimal("100000")
# Fixed deposit rates by minimum term in months, matching what the app shows
DEPOSIT_RATES = [(60, Decimal("5.5")), (36, Decimal("5.0")), (24, Decimal("4.8")), (12, Decimal("4.5")), (6, Decimal("4.0")), (1, Decimal("3.5"))]


class SavingsGoal(Base):
    __tablename__ = "savings_goals_store"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    category = Column(String(40), nullable=False, default="General")
    target_amount = Column(DECIMAL(18, 2), nullable=False)
    current_amount = Column(DECIMAL(18, 2), nullable=False, default=0)
    monthly_contribution = Column(DECIMAL(18, 2), nullable=False, default=0)
    deadline = Column(Date, nullable=False)
    is_auto_save = Column(Boolean, nullable=False, default=False)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class FixedDeposit(Base):
    __tablename__ = "fixed_deposits"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    principal = Column(DECIMAL(18, 2), nullable=False)
    rate = Column(DECIMAL(5, 2), nullable=False)
    term_months = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    maturity_date = Column(Date, nullable=False)
    auto_renew = Column(Boolean, nullable=False, default=False)
    roundup_enabled = Column(Boolean, nullable=False, default=False)
    # active, matured (paid out with interest) or broken (closed early, principal only)
    status = Column(String(10), nullable=False, default="active")
    closed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AutoSavePlan(Base):
    __tablename__ = "auto_save_plans"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    amount = Column(DECIMAL(18, 2), nullable=False)
    frequency = Column(String(8), nullable=False)
    next_run = Column(Date, nullable=False)
    saved_total = Column(DECIMAL(18, 2), nullable=False, default=0)
    runs = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    last_status = Column(String(120))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ---------- Requests ----------

class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    targetAmount: Decimal = Field(gt=0, le=Decimal("10000000"))
    monthlyContribution: Decimal = Field(ge=0, le=Decimal("1000000"))
    category: str = Field(default="General", max_length=40)
    deadline: Optional[date] = None
    isAutoSave: bool = False


class GoalUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    targetAmount: Optional[Decimal] = Field(default=None, gt=0, le=Decimal("10000000"))
    monthlyContribution: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("1000000"))
    category: Optional[str] = Field(default=None, max_length=40)
    deadline: Optional[date] = None
    isAutoSave: Optional[bool] = None


class MoneyMove(BaseModel):
    amount: Decimal = Field(gt=0, le=MAX_MOVE, decimal_places=2)


class DepositCreate(BaseModel):
    amount: Decimal = Field(gt=0, le=MAX_MOVE, decimal_places=2)
    termMonths: int = Field(ge=1, le=120)
    autoRenew: bool = False
    roundupEnabled: bool = False


class PlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    amount: Decimal = Field(gt=0, le=Decimal("10000"), decimal_places=2)
    frequency: Literal["DAILY", "WEEKLY", "MONTHLY"]
    startDate: Optional[date] = None


class PlanUpdate(BaseModel):
    isActive: bool


# ---------- Money movement ----------

def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def take_cash(db: Session, user_id: str, amount: Decimal, description: str, reference: str) -> None:
    """Move cash out of the user's account into savings, or refuse when there isn't enough."""
    source = (
        cash_accounts(db, user_id).filter(Account.available_balance >= amount)
        .order_by(Account.is_primary.desc(), Account.available_balance.desc()).with_for_update().first()
    )
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Not enough cash. This needs ${amount:,.2f} and your Hoardrun cash is ${cash_balance(db, user_id):,.2f}. Add money first.",
        )
    source.available_balance = Decimal(source.available_balance) - amount
    source.current_balance = Decimal(source.current_balance) - amount
    record(db, user_id, source, amount, TransactionTypeEnum.TRANSFER_OUT, TransactionDirectionEnum.OUTBOUND, description, reference)


def give_cash(db: Session, user_id: str, amount: Decimal, description: str, reference: str) -> None:
    """Move money from savings back into the user's cash account."""
    destination = cash_account(db, user_id, "USD")
    destination.available_balance = Decimal(destination.available_balance) + amount
    destination.current_balance = Decimal(destination.current_balance) + amount
    record(db, user_id, destination, amount, TransactionTypeEnum.TRANSFER_IN, TransactionDirectionEnum.INBOUND, description, reference)


def record(db, user_id, account, amount, kind, direction, description, reference) -> None:
    now = datetime.now(timezone.utc)
    db.add(Transaction(
        id=str(uuid.uuid4()), user_id=user_id, account_id=account.id, transaction_type=kind, direction=direction,
        status=TransactionStatusEnum.COMPLETED, amount=amount, currency="USD", payment_method=PaymentMethodEnum.OTHER,
        description=description, merchant_name="Hoardrun Savings", reference_number=reference,
        transaction_date=now, posted_date=now, balance_after=account.current_balance,
    ))


def ref(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


# ---------- Rules ----------

def deposit_rate(term_months: int) -> Decimal:
    return next(rate for minimum, rate in DEPOSIT_RATES if term_months >= minimum)


def add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def deposit_interest(deposit: FixedDeposit) -> Decimal:
    return money(Decimal(deposit.principal) * Decimal(deposit.rate) / 100 * Decimal(deposit.term_months) / 12)


def next_run_after(day: date, frequency: str) -> date:
    if frequency == "DAILY":
        return day + timedelta(days=1)
    if frequency == "WEEKLY":
        return day + timedelta(weeks=1)
    return add_months(day, 1)


def settle(db: Session, user_id: str) -> None:
    """Catch up everything that has fallen due: matured deposits pay out, auto-save plans run."""
    today = date.today()
    changed = False
    for deposit in db.query(FixedDeposit).filter(FixedDeposit.user_id == user_id, FixedDeposit.status == "active",
                                                 FixedDeposit.maturity_date <= today).all():
        payout = money(Decimal(deposit.principal) + deposit_interest(deposit))
        give_cash(db, user_id, payout, f"Fixed deposit matured ({deposit.term_months} months at {deposit.rate}%)", ref("FD"))
        if deposit.auto_renew:
            # Renewal locks the principal again at today's rate for the same term; the interest stays in cash
            take_cash(db, user_id, money(deposit.principal), "Fixed deposit renewed", ref("FD"))
            db.add(FixedDeposit(
                id=str(uuid.uuid4()), user_id=user_id, principal=deposit.principal, rate=deposit_rate(deposit.term_months),
                term_months=deposit.term_months, start_date=today, maturity_date=add_months(today, deposit.term_months),
                auto_renew=True, roundup_enabled=deposit.roundup_enabled,
            ))
        deposit.status = "matured"
        deposit.closed_at = datetime.utcnow()
        notify(db, user_id, "success", "Fixed deposit paid out",
               f"${payout:,.2f} is back in your cash, including ${deposit_interest(deposit):,.2f} interest."
               + (" It renewed for another term." if deposit.auto_renew else ""), link="/savings", key=f"fd-matured:{deposit.id}", email=True)
        changed = True

    for plan in db.query(AutoSavePlan).filter(AutoSavePlan.user_id == user_id, AutoSavePlan.is_active.is_(True),
                                              AutoSavePlan.next_run <= today).all():
        # At most a year of missed runs, so a long-forgotten daily plan can't drain the account in one go
        for _ in range(366):
            if plan.next_run > today:
                break
            amount = money(plan.amount)
            if cash_balance(db, user_id) < amount:
                plan.last_status = f"Skipped {plan.next_run:%b %d}: not enough cash"
                notify(db, user_id, "warning", f"Auto-save skipped: {plan.name}",
                       f"There wasn't ${amount:,.2f} in your cash on {plan.next_run:%b %d}. Add money to keep it going.",
                       link="/savings", key=f"autosave-skip:{plan.id}:{plan.next_run.isoformat()}", email=True)
            else:
                take_cash(db, user_id, amount, f"Auto-save: {plan.name}", ref("AS"))
                plan.saved_total = money(Decimal(plan.saved_total) + amount)
                plan.runs += 1
                plan.last_status = f"Saved ${amount:,.2f} on {plan.next_run:%b %d}"
            plan.next_run = next_run_after(plan.next_run, plan.frequency)
        changed = True

    if changed:
        db.commit()


# ---------- Serializers ----------

def goal_out(goal: SavingsGoal) -> dict:
    target = Decimal(goal.target_amount)
    current = Decimal(goal.current_amount)
    return {
        "id": goal.id,
        "name": goal.name,
        "category": goal.category,
        "targetAmount": float(target),
        "currentAmount": float(current),
        "monthlyContribution": float(goal.monthly_contribution),
        "deadline": goal.deadline.isoformat(),
        "isAutoSave": goal.is_auto_save,
        "isCompleted": goal.completed_at is not None,
        "progress": float(min(current / target * 100, Decimal(100))) if target else 0.0,
        "createdAt": goal.created_at.isoformat(),
        "updatedAt": goal.updated_at.isoformat(),
    }


def deposit_out(deposit: FixedDeposit) -> dict:
    interest = deposit_interest(deposit)
    return {
        "id": deposit.id,
        "amount": float(deposit.principal),
        "rate": float(deposit.rate),
        "term": deposit.term_months,
        "startDate": deposit.start_date.isoformat(),
        "maturityDate": deposit.maturity_date.isoformat(),
        "interest": float(interest),
        "maturityAmount": float(money(Decimal(deposit.principal) + interest)),
        "autoRenew": deposit.auto_renew,
        "roundupEnabled": deposit.roundup_enabled,
        "status": deposit.status,
    }


def plan_out(plan: AutoSavePlan) -> dict:
    return {
        "id": plan.id,
        "name": plan.name,
        "amount": float(plan.amount),
        "frequency": plan.frequency,
        "nextRun": plan.next_run.isoformat(),
        "savedTotal": float(plan.saved_total),
        "runs": plan.runs,
        "isActive": plan.is_active,
        "lastStatus": plan.last_status,
    }


def own_goal(db: Session, user_id: str, goal_id: str) -> SavingsGoal:
    goal = db.query(SavingsGoal).filter(SavingsGoal.id == goal_id, SavingsGoal.user_id == user_id).with_for_update().first()
    if goal is None:
        raise HTTPException(status_code=404, detail="Savings goal not found")
    return goal


# ---------- Goals ----------

@router.get("/goals")
async def list_goals(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    settle(db, user_id)
    goals = db.query(SavingsGoal).filter(SavingsGoal.user_id == user_id).order_by(SavingsGoal.created_at.desc()).all()
    return [goal_out(g) for g in goals]


@router.post("/goals", status_code=status.HTTP_201_CREATED)
async def create_goal(payload: GoalCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    deadline = payload.deadline or add_months(date.today(), 12)
    if deadline <= date.today():
        raise HTTPException(status_code=400, detail="Pick a target date in the future.")
    goal = SavingsGoal(
        id=str(uuid.uuid4()), user_id=user_id, name=payload.name.strip(), category=(payload.category or "General").strip() or "General",
        target_amount=money(payload.targetAmount), monthly_contribution=money(payload.monthlyContribution),
        deadline=deadline, is_auto_save=payload.isAutoSave,
    )
    db.add(goal)
    db.commit()
    return goal_out(goal)


@router.patch("/goals/{goal_id}")
async def update_goal(goal_id: str, payload: GoalUpdate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    goal = own_goal(db, user_id, goal_id)
    if payload.name is not None:
        goal.name = payload.name.strip()
    if payload.category is not None:
        goal.category = payload.category.strip() or "General"
    if payload.targetAmount is not None:
        goal.target_amount = money(payload.targetAmount)
    if payload.monthlyContribution is not None:
        goal.monthly_contribution = money(payload.monthlyContribution)
    if payload.deadline is not None:
        if payload.deadline <= date.today():
            raise HTTPException(status_code=400, detail="Pick a target date in the future.")
        goal.deadline = payload.deadline
    if payload.isAutoSave is not None:
        goal.is_auto_save = payload.isAutoSave
    goal.completed_at = goal.completed_at if Decimal(goal.current_amount) >= Decimal(goal.target_amount) else None
    db.commit()
    return goal_out(goal)


@router.post("/goals/{goal_id}/contribute")
async def contribute(goal_id: str, payload: MoneyMove, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    goal = own_goal(db, user_id, goal_id)
    amount = money(payload.amount)
    take_cash(db, user_id, amount, f"Saved to {goal.name}", ref("SG"))
    goal.current_amount = money(Decimal(goal.current_amount) + amount)
    if goal.completed_at is None and Decimal(goal.current_amount) >= Decimal(goal.target_amount):
        goal.completed_at = datetime.utcnow()
        notify(db, user_id, "success", f"Goal reached: {goal.name}",
               f"You saved ${Decimal(goal.current_amount):,.2f}. Nice work.", link="/savings", key=f"goal-done:{goal.id}")
    db.commit()
    return {**goal_out(goal), "cashAvailable": float(cash_balance(db, user_id))}


@router.post("/goals/{goal_id}/withdraw")
async def withdraw(goal_id: str, payload: MoneyMove, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    goal = own_goal(db, user_id, goal_id)
    amount = money(payload.amount)
    if amount > Decimal(goal.current_amount):
        raise HTTPException(status_code=400, detail=f"This goal holds ${Decimal(goal.current_amount):,.2f}.")
    goal.current_amount = money(Decimal(goal.current_amount) - amount)
    if Decimal(goal.current_amount) < Decimal(goal.target_amount):
        goal.completed_at = None
    give_cash(db, user_id, amount, f"Moved from {goal.name}", ref("SG"))
    db.commit()
    return {**goal_out(goal), "cashAvailable": float(cash_balance(db, user_id))}


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    goal = own_goal(db, user_id, goal_id)
    returned = money(goal.current_amount)
    if returned > 0:
        give_cash(db, user_id, returned, f"Closed goal {goal.name}", ref("SG"))
    db.delete(goal)
    db.commit()
    return {"deleted": True, "returnedToCash": float(returned)}


# ---------- Fixed deposits ----------

@router.get("/fixed-deposits")
async def list_deposits(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    settle(db, user_id)
    deposits = db.query(FixedDeposit).filter(FixedDeposit.user_id == user_id).order_by(FixedDeposit.created_at.desc()).all()
    return [deposit_out(d) for d in deposits]


@router.post("/fixed-deposits", status_code=status.HTTP_201_CREATED)
async def open_deposit(payload: DepositCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    amount = money(payload.amount)
    if amount < Decimal("10"):
        raise HTTPException(status_code=400, detail="A fixed deposit starts at $10.")
    take_cash(db, user_id, amount, f"Fixed deposit for {payload.termMonths} months", ref("FD"))
    today = date.today()
    deposit = FixedDeposit(
        id=str(uuid.uuid4()), user_id=user_id, principal=amount, rate=deposit_rate(payload.termMonths),
        term_months=payload.termMonths, start_date=today, maturity_date=add_months(today, payload.termMonths),
        auto_renew=payload.autoRenew, roundup_enabled=payload.roundupEnabled,
    )
    db.add(deposit)
    db.commit()
    return {**deposit_out(deposit), "cashAvailable": float(cash_balance(db, user_id))}


@router.post("/fixed-deposits/{deposit_id}/break")
async def break_deposit(deposit_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Closing early returns the principal only; interest is earned at maturity."""
    deposit = db.query(FixedDeposit).filter(FixedDeposit.id == deposit_id, FixedDeposit.user_id == user_id).with_for_update().first()
    if deposit is None:
        raise HTTPException(status_code=404, detail="Fixed deposit not found")
    if deposit.status != "active":
        raise HTTPException(status_code=400, detail="This deposit is already closed.")
    give_cash(db, user_id, money(deposit.principal), "Fixed deposit closed early", ref("FD"))
    deposit.status = "broken"
    deposit.closed_at = datetime.utcnow()
    db.commit()
    return {**deposit_out(deposit), "cashAvailable": float(cash_balance(db, user_id))}


# ---------- Auto-save ----------

@router.get("/automated-savings")
async def list_plans(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    settle(db, user_id)
    plans = db.query(AutoSavePlan).filter(AutoSavePlan.user_id == user_id).order_by(AutoSavePlan.created_at.desc()).all()
    return [plan_out(p) for p in plans]


@router.post("/automated-savings", status_code=status.HTTP_201_CREATED)
async def create_plan(payload: PlanCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    start = payload.startDate or date.today()
    if start < date.today():
        raise HTTPException(status_code=400, detail="Start today or later.")
    plan = AutoSavePlan(
        id=str(uuid.uuid4()), user_id=user_id, name=payload.name.strip(), amount=money(payload.amount),
        frequency=payload.frequency, next_run=start,
    )
    db.add(plan)
    db.commit()
    settle(db, user_id)
    return plan_out(plan)


@router.patch("/automated-savings/{plan_id}")
async def update_plan(plan_id: str, payload: PlanUpdate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    plan = db.query(AutoSavePlan).filter(AutoSavePlan.id == plan_id, AutoSavePlan.user_id == user_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="Auto-save plan not found")
    plan.is_active = payload.isActive
    if plan.is_active and plan.next_run < date.today():
        # Resuming starts from today rather than catching up the paused period
        plan.next_run = date.today()
    db.commit()
    settle(db, user_id)
    return plan_out(plan)


@router.delete("/automated-savings/{plan_id}")
async def delete_plan(plan_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    plan = db.query(AutoSavePlan).filter(AutoSavePlan.id == plan_id, AutoSavePlan.user_id == user_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="Auto-save plan not found")
    returned = money(plan.saved_total)
    if returned > 0:
        give_cash(db, user_id, returned, f"Closed auto-save {plan.name}", ref("AS"))
    db.delete(plan)
    db.commit()
    return {"deleted": True, "returnedToCash": float(returned)}


# ---------- Summary ----------

def totals(db: Session, user_id: str):
    goals = db.query(SavingsGoal).filter(SavingsGoal.user_id == user_id).all()
    deposits = db.query(FixedDeposit).filter(FixedDeposit.user_id == user_id, FixedDeposit.status == "active").all()
    plans = db.query(AutoSavePlan).filter(AutoSavePlan.user_id == user_id).all()
    return goals, deposits, plans


@router.get("/stats")
async def stats(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    settle(db, user_id)
    goals, deposits, plans = totals(db, user_id)
    in_goals = sum((Decimal(g.current_amount) for g in goals), Decimal(0))
    in_deposits = sum((Decimal(d.principal) for d in deposits), Decimal(0))
    in_plans = sum((Decimal(p.saved_total) for p in plans), Decimal(0))
    total = in_goals + in_deposits + in_plans

    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)
    moves = db.query(Transaction).filter(Transaction.user_id == user_id, Transaction.merchant_name == "Hoardrun Savings",
                                         Transaction.created_at >= month_start).all()
    saved_this_month = sum((Decimal(t.amount) if t.direction == TransactionDirectionEnum.OUTBOUND else -Decimal(t.amount) for t in moves), Decimal(0))

    remaining = [Decimal(g.target_amount) - Decimal(g.current_amount) for g in goals if g.completed_at is None]
    next_milestone = min(remaining) if remaining else Decimal(0)

    per_month = sum((Decimal(g.monthly_contribution) for g in goals if g.completed_at is None), Decimal(0))
    per_month += sum((Decimal(p.amount) * {"DAILY": Decimal(30), "WEEKLY": Decimal("4.33"), "MONTHLY": Decimal(1)}[p.frequency]
                      for p in plans if p.is_active), Decimal(0))
    deposit_interest_year = sum((deposit_interest(d) * 12 / d.term_months for d in deposits), Decimal(0))
    projected = total + per_month * 12 + deposit_interest_year

    return {
        "total_savings": float(money(total)),
        "monthly_growth": float(money(saved_this_month)),
        "next_milestone": float(money(next_milestone)),
        "projected_savings": float(money(projected)),
        "in_goals": float(money(in_goals)),
        "in_fixed_deposits": float(money(in_deposits)),
        "in_auto_save": float(money(in_plans)),
    }


@router.get("/insights")
async def insights(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    settle(db, user_id)
    goals, deposits, plans = totals(db, user_id)
    cash = cash_balance(db, user_id)
    tips: List[str] = []
    for goal in goals:
        if goal.completed_at is not None:
            continue
        remaining = Decimal(goal.target_amount) - Decimal(goal.current_amount)
        months_left = max((goal.deadline.year - date.today().year) * 12 + goal.deadline.month - date.today().month, 1)
        needed = money(remaining / months_left)
        if Decimal(goal.monthly_contribution) < needed:
            tips.append(f"To reach {goal.name} by {goal.deadline:%B %Y}, save about ${needed:,.2f} a month (you planned ${Decimal(goal.monthly_contribution):,.2f}).")
    if not goals:
        tips.append("Set your first goal to see how long it will take and what to put away each month.")
    if cash >= Decimal("100") and not deposits:
        tips.append(f"You have ${cash:,.2f} in cash. Money you won't need for a while can earn {deposit_rate(12)}% a year in a 12-month fixed deposit.")
    if not plans:
        tips.append("An auto-save plan moves a set amount into savings for you every day, week or month.")
    return {"recommendations": tips}
