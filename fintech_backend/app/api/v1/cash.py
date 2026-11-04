"""
Instant sends between Hoardrun users: cash moves from one member's Hoardrun cash
account to another's in one database transaction, with a record on both sides.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Column, DateTime, DECIMAL, ForeignKey, String, func
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...database.config import Base, get_db
from ...database.models import (
    Account, MerchantCategoryEnum, PaymentMethodEnum, Transaction, TransactionDirectionEnum, TransactionStatusEnum,
    TransactionTypeEnum, User,
)
from ...services.deposit_ledger import cash_account
from ...services.inbox import notify
from .budgets_store import check_alerts
from .identity import require_verified_identity
from .venture import cash_accounts, cash_balance

router = APIRouter(prefix="/cash", tags=["cash"])

CENT = Decimal("0.01")
MAX_SEND = Decimal("10000")


class CashTransfer(Base):
    __tablename__ = "cash_transfers"

    id = Column(String, primary_key=True)
    sender_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(DECIMAL(18, 2), nullable=False)
    note = Column(String(140))
    reference = Column(String(20), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SendCash(BaseModel):
    recipient_email: EmailStr
    amount: Decimal = Field(gt=0, decimal_places=2)
    note: Optional[str] = Field(default=None, max_length=140)


def public_name(user: User) -> str:
    last = (user.last_name or "").strip()
    return f"{(user.first_name or 'Hoardrun member').strip()} {last[:1] + '.' if last else ''}".strip()


def find_user(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()


@router.get("/balance")
async def balance(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return {"cash_available": float(cash_balance(db, user_id))}


@router.get("/lookup")
async def lookup(email: EmailStr = Query(...), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = find_user(db, email)
    if user is None or user.id == user_id:
        return {"found": False}
    return {"found": True, "name": public_name(user)}


@router.get("/recent")
async def recent(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    rows = (
        db.query(CashTransfer.recipient_user_id, func.max(CashTransfer.created_at).label("last"))
        .filter(CashTransfer.sender_user_id == user_id)
        .group_by(CashTransfer.recipient_user_id)
        .order_by(func.max(CashTransfer.created_at).desc())
        .limit(8)
        .all()
    )
    users = {u.id: u for u in db.query(User).filter(User.id.in_([row[0] for row in rows]))} if rows else {}
    return {"data": [{"name": public_name(users[row[0]]), "email": users[row[0]].email} for row in rows if row[0] in users]}


@router.post("/send", status_code=status.HTTP_201_CREATED)
async def send(payload: SendCash, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    amount = payload.amount.quantize(CENT)
    if amount < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The smallest send is $1")
    if amount > MAX_SEND:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"You can send up to ${MAX_SEND:,.0f} at a time")
    recipient = find_user(db, payload.recipient_email)
    if recipient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No one on Hoardrun uses that email")
    if recipient.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You can't send money to yourself")
    require_verified_identity(db, user_id, "send money")
    sender = db.get(User, user_id)

    source = (
        cash_accounts(db, user_id).filter(Account.available_balance >= amount)
        .order_by(Account.is_primary.desc(), Account.available_balance.desc()).with_for_update().first()
    )
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Not enough cash. You're sending ${amount:,.2f} and your Hoardrun cash is ${cash_balance(db, user_id):,.2f}. Add money first.",
        )
    destination = cash_account(db, recipient.id, "USD")
    now = datetime.now(timezone.utc)
    reference = f"HS-{uuid.uuid4().hex[:12].upper()}"
    note = (payload.note or "").strip() or None

    source.available_balance = Decimal(source.available_balance) - amount
    source.current_balance = Decimal(source.current_balance) - amount
    destination.available_balance = Decimal(destination.available_balance) + amount
    destination.current_balance = Decimal(destination.current_balance) + amount
    # Labelled as transfers so sends count toward a "Sending money" budget
    common = dict(status=TransactionStatusEnum.COMPLETED, amount=amount, currency="USD", payment_method=PaymentMethodEnum.OTHER,
                  merchant_category=MerchantCategoryEnum.TRANSFER,
                  transaction_date=now, posted_date=now, notes=note)
    db.add(Transaction(
        id=str(uuid.uuid4()), user_id=user_id, account_id=source.id, transaction_type=TransactionTypeEnum.TRANSFER_OUT,
        direction=TransactionDirectionEnum.OUTBOUND, description=f"Sent to {public_name(recipient)}",
        merchant_name=public_name(recipient), reference_number=f"{reference}-O", balance_after=source.current_balance, **common,
    ))
    db.add(Transaction(
        id=str(uuid.uuid4()), user_id=recipient.id, account_id=destination.id, transaction_type=TransactionTypeEnum.TRANSFER_IN,
        direction=TransactionDirectionEnum.INBOUND, description=f"From {public_name(sender) if sender else 'a Hoardrun member'}",
        merchant_name=public_name(sender) if sender else None, reference_number=f"{reference}-I", balance_after=destination.current_balance, **common,
    ))
    db.add(CashTransfer(id=str(uuid.uuid4()), sender_user_id=user_id, recipient_user_id=recipient.id, amount=amount, note=note, reference=reference))
    sender_name = public_name(sender) if sender else "a Hoardrun member"
    notify(db, recipient.id, "transaction", f"You received ${amount:,.2f}",
           f"From {sender_name}" + (f": \"{note}\"" if note else "."), link="/transactions", key=f"cash-in:{reference}", email=True)
    notify(db, user_id, "transaction", f"Sent ${amount:,.2f} to {public_name(recipient)}",
           "It's in their Hoardrun account now.", link="/transactions", key=f"cash-out:{reference}", email=True)
    db.commit()
    check_alerts(db, user_id)
    return {
        "data": {
            "reference": reference,
            "amount": float(amount),
            "recipient_name": public_name(recipient),
            "note": note,
            "sent_at": now.isoformat(),
            "cash_available": float(cash_balance(db, user_id)),
        }
    }
