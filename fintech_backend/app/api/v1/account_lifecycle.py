"""
Your data and closing your account.

Export gives the user everything Hoardrun holds about them. Closing is permanent: personal
details are scrubbed and sign-in stops working, but transaction records are kept, as
financial record-keeping rules require. An account can only close once it holds no money.
"""

import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...auth import passwords
from ...auth.dependencies import get_current_user_id
from ...database.circle_models import CircleMember
from ...database.config import get_db
from ...database.listing_models import CompanyListing
from ...database.market_models import MarketPosition
from ...database.models import Account, AccountStatusEnum, Transaction, User
from ...database.venture_models import FundShareOrder, VentureFund
from ...services.card_vault import SavedCard
from ...services.email_service import goodbye_email, queue
from ...services.inbox import Notification, NotificationPrefs
from ...services.wealth import wealth
from .bank_links import BankLink, BankLinkAccount, BankTransfer, unlink_all
from .budgets_store import Budget
from .google_auth import UserIdentity
from .identity import IdentityCheck
from .issued_cards import IssuedCard, cancel_all_cards
from .brokerage import BrokerageAccount, BrokerOrder
from .savings_store import AutoSavePlan, FixedDeposit, SavingsGoal

router = APIRouter(prefix="/account", tags=["account"])


class CloseRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    # Typed by the person, so closing can't happen by a stray tap
    confirm: Literal["CLOSE"]


def plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return getattr(value, "value", value)


def rows(items, fields):
    return [{field: plain(getattr(item, field, None)) for field in fields} for item in items]


@router.get("/export")
async def export_data(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    mine = lambda model, column="user_id": db.query(model).filter(getattr(model, column) == user_id).all()  # noqa: E731
    owned = wealth(db, user_id)
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile": rows([user], ["id", "email", "first_name", "last_name", "phone_number", "country", "date_of_birth", "bio", "status", "created_at"])[0],
        "summary": {key: float(value) for key, value in owned.items()},
        "accounts": rows(mine(Account), ["id", "account_name", "account_type", "currency", "current_balance", "available_balance", "status", "created_at"]),
        "transactions": rows(db.query(Transaction).filter(Transaction.user_id == user_id).order_by(Transaction.created_at).all(),
                             ["id", "created_at", "transaction_type", "direction", "status", "amount", "currency", "description", "merchant_name", "merchant_category", "reference_number"]),
        "savings_goals": rows(mine(SavingsGoal), ["id", "name", "category", "target_amount", "current_amount", "monthly_contribution", "deadline", "completed_at", "created_at"]),
        "fixed_deposits": rows(mine(FixedDeposit), ["id", "principal", "rate", "term_months", "start_date", "maturity_date", "status", "created_at"]),
        "auto_save_plans": rows(mine(AutoSavePlan), ["id", "name", "amount", "frequency", "saved_total", "runs", "is_active", "created_at"]),
        "budgets": rows(mine(Budget), ["id", "name", "category", "monthly_limit", "created_at"]),
        "linked_banks": rows(mine(BankLink), ["id", "institution_name", "status", "created_at"]),
        "linked_bank_accounts": rows(mine(BankLinkAccount), ["id", "name", "mask", "kind", "subtype"]),
        "bank_transfers": rows(mine(BankTransfer), ["id", "direction", "amount", "status", "account_label", "failure_reason", "created_at"]),
        "sign_in_methods": rows(mine(UserIdentity), ["provider", "email", "created_at"]),
        "identity_check": rows(mine(IdentityCheck), ["state", "verified_at", "created_at"]),
        "investing_account": rows(mine(BrokerageAccount), ["status", "uninvested_cash", "created_at"]),
        "broker_orders": rows(mine(BrokerOrder), ["asset_type", "symbol", "side", "notional", "status", "filled_qty", "filled_avg_price", "created_at"]),
        "hoardrun_cards": rows(mine(IssuedCard), ["last4", "brand", "exp_month", "exp_year", "status", "monthly_limit", "created_at"]),
        "cards": rows(mine(SavedCard), ["id", "kind", "brand", "last4", "exp_month", "exp_year", "status", "source", "created_at"]),
        "market_positions": rows(mine(MarketPosition), ["asset_type", "symbol", "quantity", "cost_basis"]),
        "venture_fund_purchases": rows(mine(FundShareOrder), ["fund_id", "shares", "share_price", "amount", "created_at"]),
        "circle_memberships": rows(mine(CircleMember), ["circle_id", "contributed", "joined_at"]),
        "company_listings": rows(mine(CompanyListing, "owner_user_id"), ["id", "name", "category", "sector"]),
        "notifications": rows(mine(Notification), ["created_at", "kind", "title", "message"]),
    }


@router.get("/close-check")
async def close_check(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """What has to happen before this account can close."""
    return {"blockers": blockers(db, user_id)}


def blockers(db: Session, user_id: str):
    owned = wealth(db, user_id)
    reasons = []
    labels = [("cash", "in cash"), ("savings", "in savings"), ("investments", "in investments")]
    for key, label in labels:
        if owned[key] > 0:
            reasons.append(f"${owned[key]:,.2f} {label}")
    moving = db.query(BankTransfer).filter(BankTransfer.user_id == user_id, BankTransfer.undone.is_(False),
                                           BankTransfer.status.in_(["pending", "posted"])).count()
    if moving:
        reasons.append(f"{moving} bank transfer{'s' if moving > 1 else ''} still on the way")
    managed = db.query(VentureFund).filter(VentureFund.manager_user_id == user_id, VentureFund.shares_sold > 0).count()
    if managed:
        reasons.append(f"{managed} venture fund{'s' if managed > 1 else ''} with investors that you manage")
    return reasons


@router.post("/close")
async def close_account(payload: CloseRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if user is None or user.status == "deactivated":
        raise HTTPException(status_code=404, detail="Account not found")
    if not passwords.verify_password(payload.password, user.password_hash or ""):
        raise HTTPException(status_code=401, detail="That password isn't right.")
    reasons = blockers(db, user_id)
    if reasons:
        raise HTTPException(
            status_code=409,
            detail="Your account still holds " + "; ".join(reasons) + ". Move or close these first, then try again.",
        )

    # Things only the user cares about go; financial records stay. Plaid is told to forget their banks.
    unlink_all(db, user_id)
    cancel_all_cards(db, user_id)
    for model, column in ((SavedCard, "user_id"), (Notification, "user_id"), (NotificationPrefs, "user_id"), (UserIdentity, "user_id"), (Budget, "user_id"), (SavingsGoal, "user_id"),
                          (AutoSavePlan, "user_id"), (CompanyListing, "owner_user_id")):
        db.query(model).filter(getattr(model, column) == user_id).delete(synchronize_session=False)
    db.query(CircleMember).filter(CircleMember.user_id == user_id, CircleMember.contributed == 0).delete(synchronize_session=False)
    db.query(VentureFund).filter(VentureFund.manager_user_id == user_id, VentureFund.shares_sold == 0).delete(synchronize_session=False)
    db.query(Account).filter(Account.user_id == user_id).update({Account.status: AccountStatusEnum.CLOSED}, synchronize_session=False)

    # A last email to the address on file, sent once this commits
    queue(db, user.email, *goodbye_email(user.first_name))
    # Personal details scrubbed; the email is freed so the person could join again later
    user.email = f"closed-{user.id}@closed.hoardrun.invalid"
    user.first_name, user.last_name = "Closed", "account"
    user.phone_number = user.date_of_birth = user.id_number = user.bio = user.profile_picture_url = None
    user.password_hash = passwords.hash_password(secrets.token_urlsafe(32))
    user.password_reset_token = user.email_verification_code = None
    # The users table allows pending, active, suspended or deactivated; closing is deactivated
    user.status = "deactivated"
    user.is_active = False
    db.commit()
    return {"closed": True}
