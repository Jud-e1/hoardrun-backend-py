"""
Saved cards and their settings, stored in the database.

Cards arrive two ways: typed in on the Cards page (display details only), or saved automatically
from a real Add money payment. Lock, contactless, online payments and limits are kept per card;
they control Hoardrun-issued cards once card issuing is connected.
"""

import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...database.config import get_db
from ...database.models import Transaction
from ...services.card_vault import SavedCard, card_tag, normalise_brand

router = APIRouter(prefix="/payment-methods", tags=["Payment Methods"])


class CardCreate(BaseModel):
    type: Literal["debit_card", "credit_card"] = "debit_card"
    card_holder_name: str = Field(min_length=2, max_length=80)
    # Only the last four digits ever reach the server, e.g. "****4242"
    card_number_masked: str = Field(min_length=4, max_length=24)
    expiry_month: int = Field(ge=1, le=12)
    expiry_year: int = Field(ge=2000, le=2100)
    card_type: str = Field(default="visa", max_length=20)
    status: Optional[str] = None
    plaid_account_id: Optional[str] = None


class CardUpdate(BaseModel):
    status: Optional[Literal["active", "locked"]] = None
    contactless: Optional[bool] = None
    online_payments: Optional[bool] = None
    # Zero or null clears a limit
    per_transaction_limit: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("1000000"))
    monthly_limit: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("1000000"))
    card_holder_name: Optional[str] = Field(default=None, min_length=2, max_length=80)


def last_four(masked: str) -> str:
    digits = re.sub(r"\D", "", masked)
    # Refuse anything that looks like a full card number, so one can never be stored by mistake
    if len(digits) != 4:
        raise HTTPException(status_code=400, detail="Send only the last four digits of the card.")
    return digits


def card_out(card: SavedCard) -> dict:
    return {
        "id": card.id,
        "type": card.kind,
        "card_holder_name": card.holder_name,
        "card_number_masked": f"****{card.last4}",
        "expiry_month": card.exp_month,
        "expiry_year": card.exp_year,
        "card_type": card.brand,
        "bank": card.bank,
        "source": card.source,
        "status": card.status,
        "is_default": card.is_default,
        "contactless": card.contactless,
        "online_payments": card.online_payments,
        "per_transaction_limit": float(card.per_transaction_limit) if card.per_transaction_limit else None,
        "monthly_limit": float(card.monthly_limit) if card.monthly_limit else None,
        "last_used_at": card.last_used_at.isoformat() if card.last_used_at else None,
        "created_at": card.created_at.isoformat(),
    }


def own_card(db: Session, user_id: str, card_id: str) -> SavedCard:
    card = db.query(SavedCard).filter(SavedCard.id == card_id, SavedCard.user_id == user_id).first()
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


def card_transactions(db: Session, user_id: str, card: SavedCard):
    tag = card_tag(card.id)
    rows = db.query(Transaction).filter(Transaction.user_id == user_id, Transaction.tags.isnot(None)) \
        .order_by(Transaction.created_at.desc()).limit(500).all()
    return [t for t in rows if isinstance(t.tags, list) and tag in t.tags]


@router.get("/types")
async def payment_types():
    return [{"type": "debit_card", "label": "Debit card"}, {"type": "credit_card", "label": "Credit card"}]


@router.get("")
async def list_cards(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    cards = db.query(SavedCard).filter(SavedCard.user_id == user_id).order_by(SavedCard.is_default.desc(), SavedCard.created_at).all()
    return [card_out(c) for c in cards]


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_card(payload: CardCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    last4 = last_four(payload.card_number_masked)
    today = date.today()
    if (payload.expiry_year, payload.expiry_month) < (today.year, today.month):
        raise HTTPException(status_code=400, detail="This card has expired.")
    has_cards = db.query(SavedCard.id).filter(SavedCard.user_id == user_id).first() is not None
    card = SavedCard(
        id=str(uuid.uuid4()), user_id=user_id, kind=payload.type, holder_name=payload.card_holder_name.strip(),
        last4=last4, brand=normalise_brand(payload.card_type), exp_month=payload.expiry_month, exp_year=payload.expiry_year,
        source="manual", is_default=not has_cards,
    )
    db.add(card)
    db.commit()
    return card_out(card)


@router.put("/{card_id}")
@router.patch("/{card_id}")
async def update_card(card_id: str, payload: CardUpdate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    card = own_card(db, user_id, card_id)
    if payload.status is not None:
        card.status = payload.status
    if payload.contactless is not None:
        card.contactless = payload.contactless
    if payload.online_payments is not None:
        card.online_payments = payload.online_payments
    fields = payload.model_fields_set
    if "per_transaction_limit" in fields:
        card.per_transaction_limit = payload.per_transaction_limit or None
    if "monthly_limit" in fields:
        card.monthly_limit = payload.monthly_limit or None
    if card.per_transaction_limit and card.monthly_limit and card.per_transaction_limit > card.monthly_limit:
        raise HTTPException(status_code=400, detail="A single payment can't be more than the monthly limit.")
    if payload.card_holder_name is not None:
        card.holder_name = payload.card_holder_name.strip()
    db.commit()
    return card_out(card)


@router.post("/{card_id}/set-default")
async def set_default(card_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    card = own_card(db, user_id, card_id)
    db.query(SavedCard).filter(SavedCard.user_id == user_id).update({SavedCard.is_default: False}, synchronize_session=False)
    card.is_default = True
    db.commit()
    return card_out(card)


@router.delete("/{card_id}")
async def remove_card(card_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    card = own_card(db, user_id, card_id)
    was_default = card.is_default
    db.delete(card)
    db.flush()
    if was_default:
        replacement = db.query(SavedCard).filter(SavedCard.user_id == user_id).order_by(SavedCard.created_at).first()
        if replacement is not None:
            replacement.is_default = True
    db.commit()
    return {"deleted": True}


@router.get("/{card_id}/transactions")
async def transactions(card_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    card = own_card(db, user_id, card_id)
    rows = card_transactions(db, user_id, card)
    total = sum((Decimal(str(t.amount)) for t in rows), Decimal(0))
    return {
        "card": card_out(card),
        "total": float(total),
        "items": [
            {
                "id": t.id,
                "date": (t.transaction_date or t.created_at).isoformat(),
                "description": t.description,
                "amount": float(t.amount),
                "direction": getattr(t.direction, "value", t.direction),
                "status": getattr(t.status, "value", t.status),
                "reference": t.reference_number,
            }
            for t in rows
        ],
    }
