"""
Linked US bank accounts through Plaid, and ACH transfers between them and Hoardrun cash.

- Linking: Plaid Link gives a public token; the server swaps it for an access token, which
  is stored encrypted and never sent to the browser.
- Add money from a bank (ACH debit): the cash is added once Plaid reports the transfer settled.
- Withdraw to a bank (ACH credit): the cash leaves right away and comes back if the transfer
  fails or is returned.
- Transfer updates come from Plaid's event feed. The webhook only prompts a fetch from Plaid,
  so a forged webhook can't change anything.

Paying someone else's bank account needs a bank partner and stays off here.
"""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, DECIMAL, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...auth.signing_key import is_production
from ...config.settings import get_settings
from ...database.config import Base, get_db
from ...database.models import (
    Account, AccountStatusEnum, PaymentMethodEnum, Transaction, TransactionDirectionEnum,
    TransactionStatusEnum, TransactionTypeEnum, User,
)
from ...services.deposit_ledger import cash_account
from ...services.inbox import notify
from ...services.plaid_gateway import PlaidError, PlaidGateway
from ...services.sealed import seal, unseal
from .identity import require_verified_identity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plaid", tags=["plaid"])

MIN_TRANSFER = Decimal("1")
MAX_TRANSFER = Decimal("10000")
STALE_AFTER = timedelta(minutes=5)
# Plaid's transfer lifecycle, in order; a failure can arrive at any point, a return even after settling
PROGRESS = ["pending", "posted", "settled", "funds_available"]
ARRIVED = {"settled", "funds_available"}
UNDONE = {"failed", "cancelled", "returned"}
SANDBOX_EVENTS = {"posted", "settled", "failed", "returned"}
NOT_YET = ("Sending to other banks isn't available yet. You can send to Hoardrun members instantly, "
           "or withdraw to your own linked bank.")


# ---------- Storage ----------

class BankLink(Base):
    """One bank login linked through Plaid (a Plaid item)."""
    __tablename__ = "bank_links"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(100), nullable=False, unique=True)
    access_token = Column(Text, nullable=False)  # sealed
    institution_id = Column(String(40))
    institution_name = Column(String(120))
    # active, needs_update (the bank wants the user to sign in again) or error
    status = Column(String(16), nullable=False, default="active")
    error_code = Column(String(60))
    last_synced_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BankLinkAccount(Base):
    """An account at a linked bank, with the balances Plaid last reported."""
    __tablename__ = "bank_link_accounts"

    id = Column(String(100), primary_key=True)  # Plaid's account_id
    link_id = Column(String, ForeignKey("bank_links.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120))
    official_name = Column(String(200))
    mask = Column(String(8))
    kind = Column(String(20))
    subtype = Column(String(30))
    available = Column(DECIMAL(18, 2))
    current = Column(DECIMAL(18, 2))
    credit_limit = Column(DECIMAL(18, 2))
    currency = Column(String(3), default="USD")
    updated_at = Column(DateTime, default=datetime.utcnow)


class BankTransfer(Base):
    """An ACH transfer between a linked bank and Hoardrun cash."""
    __tablename__ = "bank_ach_transfers"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    link_id = Column(String, ForeignKey("bank_links.id", ondelete="SET NULL"))
    account_id = Column(String(100), nullable=False)
    account_label = Column(String(160))
    direction = Column(String(10), nullable=False)  # deposit or withdrawal
    amount = Column(DECIMAL(18, 2), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    plaid_transfer_id = Column(String(100), unique=True)
    reference = Column(String(40), nullable=False, unique=True)
    failure_reason = Column(String(300))
    money_moved = Column(Boolean, nullable=False, default=False)  # the cash side has been applied
    undone = Column(Boolean, nullable=False, default=False)  # a failure or return has been handled
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class PlaidEventCursor(Base):
    """Where Hoardrun is in Plaid's transfer event feed."""
    __tablename__ = "plaid_event_cursor"

    id = Column(Integer, primary_key=True)
    last_event_id = Column(Integer, nullable=False, default=0)


# ---------- Requests ----------

class LinkTokenRequest(BaseModel):
    # Reconnect an existing bank instead of linking a new one
    connection_id: Optional[str] = None


class ExchangeRequest(BaseModel):
    public_token: str = Field(min_length=10, max_length=200)
    link_token_id: Optional[str] = None
    account_id: Optional[str] = None


class TransferRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, decimal_places=2)


class SimulateRequest(BaseModel):
    transfer_id: str
    event: str


# ---------- Plaid ----------

def get_gateway() -> PlaidGateway:
    settings = get_settings()
    if not (settings.plaid_client_id and settings.plaid_secret):
        raise HTTPException(status_code=503, detail="Bank linking isn't set up yet")
    return PlaidGateway(settings.plaid_client_id, settings.plaid_secret, settings.plaid_env)


def plaid_failed(error: PlaidError, what: str) -> HTTPException:
    logger.warning("Plaid %s failed: %s %s", what, error.code, error)
    if error.code == "ITEM_LOGIN_REQUIRED":
        return HTTPException(status_code=409, detail="Your bank needs you to sign in again. Reconnect it from Bank accounts.")
    if error.code in ("INVALID_API_KEYS", "INVALID_PRODUCT", "PRODUCTS_NOT_SUPPORTED", "INVALID_CREDENTIALS"):
        return HTTPException(status_code=503, detail="Bank linking isn't available right now.")
    return HTTPException(status_code=502, detail=error.display or "Your bank didn't respond. Try again.")


# ---------- Shapes ----------

def num(value) -> Optional[float]:
    return None if value is None else float(value)


def iso(value: Optional[datetime]) -> Optional[str]:
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def show_link(link: BankLink) -> dict:
    return {
        "connection_id": link.id, "user_id": link.user_id, "item_id": link.item_id,
        "institution_id": link.institution_id, "institution_name": link.institution_name or "Your bank",
        "status": link.status, "created_at": iso(link.created_at), "last_synced_at": iso(link.last_synced_at),
        "error_message": "Sign in to your bank again to keep it linked." if link.status == "needs_update" else None,
    }


def show_account(account: BankLinkAccount, link: BankLink) -> dict:
    return {
        "account_id": account.id, "connection_id": link.id, "institution_name": link.institution_name or "Your bank",
        "name": account.name, "official_name": account.official_name, "type": account.kind,
        "subtype": account.subtype, "mask": account.mask,
        "balances": {"available": num(account.available), "current": num(account.current) or 0,
                     "limit": num(account.credit_limit), "iso_currency_code": account.currency or "USD"},
        "created_at": iso(link.created_at), "updated_at": iso(account.updated_at),
    }


def show_transfer(transfer: BankTransfer) -> dict:
    return {
        "transfer_id": transfer.id, "direction": transfer.direction, "amount": float(transfer.amount),
        "status": transfer.status, "account_id": transfer.account_id, "account": transfer.account_label,
        "failure_reason": transfer.failure_reason, "reference": transfer.reference,
        "created_at": iso(transfer.created_at), "updated_at": iso(transfer.updated_at),
    }


def label(account: BankLinkAccount, link: BankLink) -> str:
    name = link.institution_name or account.name or "Bank"
    return f"{name} •••• {account.mask}" if account.mask else name


# ---------- Links ----------

def owned_link(db: Session, user_id: str, link_id: str) -> BankLink:
    link = db.query(BankLink).filter(BankLink.id == link_id, BankLink.user_id == user_id).first()
    if link is None:
        raise HTTPException(status_code=404, detail="That bank isn't linked")
    return link


def owned_account(db: Session, user_id: str, account_id: str) -> tuple[BankLinkAccount, BankLink]:
    account = db.query(BankLinkAccount).filter(BankLinkAccount.id == account_id, BankLinkAccount.user_id == user_id).first()
    link = db.get(BankLink, account.link_id) if account else None
    if account is None or link is None:
        raise HTTPException(status_code=404, detail="That bank account isn't linked")
    if link.status != "active":
        raise HTTPException(status_code=409, detail="Your bank needs you to sign in again. Reconnect it from Bank accounts.")
    return account, link


def refresh_link(db: Session, plaid: PlaidGateway, link: BankLink) -> int:
    """Fetch the bank's accounts and balances. Returns how many accounts there are."""
    try:
        accounts = plaid.accounts(unseal(link.access_token))
    except PlaidError as error:
        if error.code == "ITEM_LOGIN_REQUIRED":
            link.status, link.error_code = "needs_update", error.code
            db.commit()
        raise
    seen = set()
    now = datetime.utcnow()
    for data in accounts:
        seen.add(data["account_id"])
        account = db.get(BankLinkAccount, data["account_id"])
        if account is None:
            account = BankLinkAccount(id=data["account_id"], link_id=link.id, user_id=link.user_id)
            db.add(account)
        account.name, account.official_name, account.mask = data["name"], data["official_name"], data["mask"]
        account.kind, account.subtype, account.currency = data["type"], data["subtype"], data["currency"]
        account.available = None if data["available"] is None else Decimal(str(data["available"]))
        account.current = None if data["current"] is None else Decimal(str(data["current"]))
        account.credit_limit = None if data["limit"] is None else Decimal(str(data["limit"]))
        account.updated_at = now
    for old in db.query(BankLinkAccount).filter(BankLinkAccount.link_id == link.id).all():
        if old.id not in seen:
            db.delete(old)
    link.status, link.error_code, link.last_synced_at = "active", None, now
    db.commit()
    return len(seen)


def refresh_stale(db: Session, user_id: str) -> None:
    """Keep balances fresh without asking Plaid on every page view."""
    cutoff = datetime.utcnow() - STALE_AFTER
    stale = db.query(BankLink).filter(BankLink.user_id == user_id, BankLink.status == "active").all()
    stale = [link for link in stale if not link.last_synced_at or link.last_synced_at < cutoff]
    if not stale:
        return
    try:
        plaid = get_gateway()
    except HTTPException:
        return
    for link in stale:
        try:
            refresh_link(db, plaid, link)
        except PlaidError as error:
            logger.info("Couldn't refresh bank link %s: %s", link.id, error.code)


def user_links(db: Session, user_id: str) -> list[BankLink]:
    return db.query(BankLink).filter(BankLink.user_id == user_id).order_by(BankLink.created_at.asc()).all()


def user_accounts(db: Session, user_id: str, link_id: Optional[str] = None) -> list[dict]:
    query = db.query(BankLinkAccount, BankLink).join(BankLink, BankLink.id == BankLinkAccount.link_id).filter(
        BankLinkAccount.user_id == user_id)
    if link_id:
        query = query.filter(BankLink.id == link_id)
    return [show_account(account, link) for account, link in query.order_by(BankLink.created_at, BankLinkAccount.name).all()]


# ---------- Ledger ----------

def new_reference() -> str:
    return "BT-" + uuid.uuid4().hex[:20].upper()


def ledger_entry(db: Session, user_id: str, account: Account, amount: Decimal, kind: TransactionTypeEnum,
                 direction: TransactionDirectionEnum, description: str, reference: str, bank: str,
                 status: TransactionStatusEnum = TransactionStatusEnum.COMPLETED) -> Transaction:
    now = datetime.now(timezone.utc)
    entry = Transaction(
        id=str(uuid.uuid4()), user_id=user_id, account_id=account.id, transaction_type=kind, direction=direction,
        status=status, amount=amount, currency="USD", payment_method=PaymentMethodEnum.ACH,
        description=description, merchant_name=bank, reference_number=reference,
        transaction_date=now, posted_date=now, balance_after=account.current_balance,
    )
    db.add(entry)
    return entry


def take_for_withdrawal(db: Session, user_id: str, amount: Decimal) -> Account:
    source = (
        db.query(Account)
        .filter(Account.user_id == user_id, Account.currency == "USD", Account.status == AccountStatusEnum.ACTIVE,
                Account.available_balance >= amount)
        .order_by(Account.is_primary.desc(), Account.available_balance.desc()).with_for_update().first()
    )
    if source is None:
        raise HTTPException(status_code=402, detail="Not enough cash. You can withdraw up to what's in your Hoardrun cash.")
    source.available_balance = Decimal(source.available_balance) - amount
    source.current_balance = Decimal(source.current_balance) - amount
    return source


def apply_event(db: Session, transfer: BankTransfer, event: str, reason: Optional[str] = None) -> None:
    """Move a transfer along and settle the cash side exactly once."""
    if event not in PROGRESS and event not in UNDONE:
        return
    if transfer.undone:
        return
    if event in PROGRESS and transfer.status in PROGRESS and PROGRESS.index(event) <= PROGRESS.index(transfer.status):
        return
    transfer.status = event
    transfer.updated_at = datetime.utcnow()
    amount = Decimal(transfer.amount)
    bank = transfer.account_label or "your bank"
    money = f"${amount:,.2f}"

    if transfer.direction == "deposit":
        if event in ARRIVED and not transfer.money_moved:
            account = cash_account(db, transfer.user_id, "USD")
            account.current_balance = Decimal(account.current_balance) + amount
            account.available_balance = Decimal(account.available_balance) + amount
            ledger_entry(db, transfer.user_id, account, amount, TransactionTypeEnum.DEPOSIT, TransactionDirectionEnum.INBOUND,
                         f"Bank deposit · {bank}", transfer.reference + "-IN", bank)
            transfer.money_moved = True
            notify(db, transfer.user_id, "transaction", "Money added", f"{money} from {bank} is in your account.",
                   link="/home", key=f"bank-in:{transfer.id}", email=True)
        elif event in UNDONE:
            transfer.undone = True
            transfer.failure_reason = reason or transfer.failure_reason
            if transfer.money_moved:
                # Returned after the cash was added: take back what's still there
                account = (
                    db.query(Account).filter(Account.user_id == transfer.user_id, Account.currency == "USD",
                                             Account.status == AccountStatusEnum.ACTIVE)
                    .order_by(Account.available_balance.desc()).with_for_update().first()
                )
                back = min(amount, Decimal(account.available_balance)) if account else Decimal(0)
                if back > 0:
                    account.available_balance = Decimal(account.available_balance) - back
                    account.current_balance = Decimal(account.current_balance) - back
                    ledger_entry(db, transfer.user_id, account, back, TransactionTypeEnum.REFUND, TransactionDirectionEnum.OUTBOUND,
                                 f"Bank deposit returned · {bank}", transfer.reference + "-RV", bank)
                if back < amount:
                    logger.error("Bank deposit %s returned with $%s not recoverable", transfer.id, amount - back)
                notify(db, transfer.user_id, "warning", "Bank deposit returned",
                       f"Your bank returned the {money} deposit, so it was taken back out of your cash.",
                       link="/transactions", key=f"bank-in-undone:{transfer.id}", email=True)
            else:
                notify(db, transfer.user_id, "warning", "Bank deposit didn't go through",
                       f"The {money} transfer from {bank} {event}. No money was added.",
                       link="/home", key=f"bank-in-undone:{transfer.id}", email=True)
    else:
        entry = db.query(Transaction).filter(Transaction.reference_number == transfer.reference + "-OUT").first()
        if event in ARRIVED and entry is not None and entry.status == TransactionStatusEnum.PENDING:
            entry.status = TransactionStatusEnum.COMPLETED
            notify(db, transfer.user_id, "transaction", "Withdrawal arrived", f"{money} reached {bank}.",
                   link="/transactions", key=f"bank-out:{transfer.id}", email=True)
        elif event in UNDONE:
            transfer.undone = True
            transfer.failure_reason = reason or transfer.failure_reason
            if entry is not None:
                entry.status = TransactionStatusEnum.FAILED if event != "returned" else TransactionStatusEnum.REVERSED
            account = cash_account(db, transfer.user_id, "USD")
            account.current_balance = Decimal(account.current_balance) + amount
            account.available_balance = Decimal(account.available_balance) + amount
            ledger_entry(db, transfer.user_id, account, amount, TransactionTypeEnum.REFUND, TransactionDirectionEnum.INBOUND,
                         f"Withdrawal returned · {bank}", transfer.reference + "-RF", bank)
            notify(db, transfer.user_id, "warning", "Withdrawal returned",
                   f"The {money} withdrawal to {bank} {event}, so it's back in your Hoardrun cash.",
                   link="/home", key=f"bank-out-undone:{transfer.id}", email=True)


def sync_events(db: Session, plaid: PlaidGateway, pages: int = 20) -> int:
    """Read Plaid's transfer events from where Hoardrun left off. Returns how many were read."""
    cursor = db.get(PlaidEventCursor, 1)
    if cursor is None:
        cursor = PlaidEventCursor(id=1, last_event_id=0)
        db.add(cursor)
        db.commit()
    read = 0
    for _ in range(pages):
        events = plaid.events(cursor.last_event_id, 25)
        for event in events:
            transfer = (
                db.query(BankTransfer).filter(BankTransfer.plaid_transfer_id == event["transfer_id"]).with_for_update().first()
                if event.get("transfer_id") else None
            )
            if transfer is not None:
                apply_event(db, transfer, event["event_type"], event.get("failure_reason"))
            cursor.last_event_id = max(cursor.last_event_id, int(event["event_id"]))
        db.commit()
        read += len(events)
        if len(events) < 25:
            break
    return read


def sync_quietly(db: Session) -> None:
    """Catch up on transfer updates when there's no webhook (local development) or it's late."""
    try:
        sync_events(db, get_gateway())
    except HTTPException:
        pass
    except PlaidError as error:
        db.rollback()
        logger.info("Couldn't read Plaid transfer events: %s", error.code)


def start_transfer(db: Session, user_id: str, payload: TransferRequest, direction: str) -> dict:
    amount = payload.amount.quantize(Decimal("0.01"))
    if not MIN_TRANSFER <= amount <= MAX_TRANSFER:
        raise HTTPException(status_code=400, detail=f"Move between ${MIN_TRANSFER:,.0f} and ${MAX_TRANSFER:,.0f} at a time.")
    account, link = owned_account(db, user_id, payload.account_id)
    if direction == "withdrawal":
        require_verified_identity(db, user_id, "withdraw to your bank")
    plaid = get_gateway()
    user = db.get(User, user_id)
    legal_name = " ".join(part for part in (user.first_name, user.last_name) if part).strip() if user else ""
    transfer = BankTransfer(
        id=str(uuid.uuid4()), user_id=user_id, link_id=link.id, account_id=account.id, account_label=label(account, link),
        direction=direction, amount=amount, status="pending", reference=new_reference(),
    )
    if direction == "withdrawal":
        source = take_for_withdrawal(db, user_id, amount)
        ledger_entry(db, user_id, source, amount, TransactionTypeEnum.WITHDRAWAL, TransactionDirectionEnum.OUTBOUND,
                     f"Withdrawal · {transfer.account_label}", transfer.reference + "-OUT", transfer.account_label,
                     status=TransactionStatusEnum.PENDING)
    db.add(transfer)
    db.flush()

    try:
        token = unseal(link.access_token)
        authorization = plaid.authorize(access_token=token, account_id=account.id,
                                        kind="debit" if direction == "deposit" else "credit", amount=amount,
                                        legal_name=legal_name or (user.email if user else "Hoardrun customer"),
                                        idempotency_key=transfer.id)
        if authorization["decision"] != "approved":
            db.rollback()
            reason = authorization.get("reason") or "Plaid couldn't approve this transfer."
            raise HTTPException(status_code=400, detail=f"This transfer wasn't approved. {reason}")
        created = plaid.create_transfer(access_token=token, account_id=account.id,
                                        authorization_id=authorization["id"], description="Hoardrun")
    except PlaidError as error:
        db.rollback()
        raise plaid_failed(error, f"{direction} transfer")

    transfer.plaid_transfer_id = created["id"]
    transfer.status = created["status"] if created["status"] in PROGRESS else "pending"
    money = f"${amount:,.2f}"
    if direction == "deposit":
        notify(db, user_id, "transaction", "Bank transfer started",
               f"{money} is on its way from {transfer.account_label}. It's added when your bank sends it, usually in 1–3 business days.",
               link="/home", key=f"bank-in-start:{transfer.id}")
    else:
        notify(db, user_id, "transaction", "Withdrawal started",
               f"{money} is on its way to {transfer.account_label}, usually in 1–3 business days.",
               link="/transactions", key=f"bank-out-start:{transfer.id}", email=True)
    db.commit()
    return show_transfer(transfer)


# ---------- Routes: linking ----------

@router.get("/status")
async def plaid_status():
    """Whether bank linking is set up, so the app can say so instead of failing."""
    settings = get_settings()
    return {"configured": bool(settings.plaid_client_id and settings.plaid_secret),
            "sandbox": settings.plaid_env != "production"}


@router.get("/test-connection")
async def test_connection():
    return await plaid_status()


@router.post("/link-token")
async def create_link_token(payload: Optional[LinkTokenRequest] = None, user_id: str = Depends(get_current_user_id),
                            db: Session = Depends(get_db)):
    plaid = get_gateway()
    token = None
    if payload and payload.connection_id:
        token = unseal(owned_link(db, user_id, payload.connection_id).access_token)
    try:
        return plaid.link_token(user_id, webhook=get_settings().plaid_webhook_url or None, access_token=token)
    except PlaidError as error:
        raise plaid_failed(error, "link token")


@router.post("/debit-card/link-token")
async def create_debit_card_link_token(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return await create_link_token(None, user_id, db)


@router.post("/exchange-token")
async def exchange_public_token(payload: ExchangeRequest, user_id: str = Depends(get_current_user_id),
                                db: Session = Depends(get_db)):
    plaid = get_gateway()
    try:
        exchanged = plaid.exchange(payload.public_token)
        item = plaid.item(exchanged["access_token"])
    except PlaidError as error:
        raise plaid_failed(error, "token exchange")

    link = db.query(BankLink).filter(BankLink.item_id == exchanged["item_id"]).first()
    if link is not None and link.user_id != user_id:
        raise HTTPException(status_code=409, detail="This bank is linked to a different account")
    new = link is None
    if new:
        link = BankLink(id=str(uuid.uuid4()), user_id=user_id, item_id=exchanged["item_id"])
        db.add(link)
    link.access_token = seal(exchanged["access_token"])
    link.institution_id = item["institution_id"]
    link.institution_name = item["institution_name"] or link.institution_name
    link.status, link.error_code = "active", None
    db.flush()
    try:
        count = refresh_link(db, plaid, link)
    except PlaidError as error:
        db.rollback()
        raise plaid_failed(error, "accounts")
    if new:
        notify(db, user_id, "security", "Bank linked",
               f"{link.institution_name or 'Your bank'} is linked to Hoardrun. If this wasn't you, remove it and change your password.",
               link="/bank-accounts", key=f"bank-linked:{link.id}")
        db.commit()
    return {"connection_id": link.id, "item_id": link.item_id, "institution_name": link.institution_name,
            "accounts_linked": count, "accounts": user_accounts(db, user_id, link.id)}


@router.post("/debit-card/verify")
async def verify_debit_card(payload: ExchangeRequest, user_id: str = Depends(get_current_user_id),
                            db: Session = Depends(get_db)):
    """Older screens link a bank here; it's the same as linking one anywhere else."""
    return await exchange_public_token(payload, user_id, db)


@router.get("/connections")
async def get_connections(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return [show_link(link) for link in user_links(db, user_id)]


@router.get("/accounts")
async def get_accounts(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    refresh_stale(db, user_id)
    return user_accounts(db, user_id)


@router.get("/connections/{connection_id}/accounts")
async def get_connection_accounts(connection_id: str, user_id: str = Depends(get_current_user_id),
                                  db: Session = Depends(get_db)):
    owned_link(db, user_id, connection_id)
    refresh_stale(db, user_id)
    return user_accounts(db, user_id, connection_id)


@router.post("/connections/{connection_id}/sync")
async def sync_connection(connection_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    link = owned_link(db, user_id, connection_id)
    try:
        count = refresh_link(db, get_gateway(), link)
    except PlaidError as error:
        raise plaid_failed(error, "sync")
    return {"connection_id": link.id, "accounts_synced": count, "transactions_synced": 0,
            "last_synced_at": iso(link.last_synced_at)}


def bank_transactions(db: Session, user_id: str, links: list[BankLink], start: date, end: date, count: int) -> list[dict]:
    plaid = get_gateway()
    found = []
    for link in links:
        if link.status != "active":
            continue
        try:
            rows = plaid.transactions(unseal(link.access_token), start, end, count)
        except PlaidError as error:
            # Transactions are optional at link time, and Plaid needs a moment to prepare them
            if error.code in ("PRODUCT_NOT_READY", "ADDITIONAL_CONSENT_REQUIRED", "PRODUCTS_NOT_SUPPORTED", "INVALID_PRODUCT"):
                continue
            raise plaid_failed(error, "transactions")
        stamp = iso(link.last_synced_at)
        found.extend({
            "transaction_id": row["transaction_id"], "account_id": row["account_id"], "connection_id": link.id,
            "amount": row["amount"], "iso_currency_code": row["currency"], "date": row["date"], "name": row["name"],
            "merchant_name": row["merchant_name"], "pending": row["pending"], "category": row["category"],
            "created_at": stamp, "updated_at": stamp,
        } for row in rows)
    found.sort(key=lambda row: row["date"], reverse=True)
    return found[:count]


def window(start_date: Optional[date], end_date: Optional[date]) -> tuple[date, date]:
    end = end_date or date.today()
    start = start_date or end - timedelta(days=30)
    if start > end or (end - start).days > 730:
        raise HTTPException(status_code=400, detail="Pick dates up to two years apart, with the start first.")
    return start, end


@router.get("/connections/{connection_id}/transactions")
async def get_connection_transactions(connection_id: str, start_date: Optional[date] = None, end_date: Optional[date] = None,
                                      count: int = Query(100, ge=1, le=500), user_id: str = Depends(get_current_user_id),
                                      db: Session = Depends(get_db)):
    link = owned_link(db, user_id, connection_id)
    start, end = window(start_date, end_date)
    return bank_transactions(db, user_id, [link], start, end, count)


@router.get("/transactions")
async def get_transactions(start_date: Optional[date] = None, end_date: Optional[date] = None,
                           count: int = Query(100, ge=1, le=500), user_id: str = Depends(get_current_user_id),
                           db: Session = Depends(get_db)):
    start, end = window(start_date, end_date)
    links = user_links(db, user_id)
    return bank_transactions(db, user_id, links, start, end, count) if links else []


@router.delete("/connections/{connection_id}")
async def disconnect(connection_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Unlink a bank. Transfers already on their way still finish; their history stays."""
    link = owned_link(db, user_id, connection_id)
    try:
        get_gateway().remove(unseal(link.access_token))
    except (HTTPException, PlaidError) as error:
        logger.info("Plaid item removal for %s didn't complete: %s", link.id, getattr(error, "code", error))
    name = link.institution_name or "Your bank"
    db.query(BankLinkAccount).filter(BankLinkAccount.link_id == link.id).delete()
    db.query(BankTransfer).filter(BankTransfer.link_id == link.id).update({BankTransfer.link_id: None})
    db.delete(link)
    db.commit()
    return {"success": True, "message": f"{name} is no longer linked"}


def unlink_all(db: Session, user_id: str) -> None:
    """Used when an account closes: tell Plaid to forget every linked bank, then drop the links."""
    for link in user_links(db, user_id):
        try:
            get_gateway().remove(unseal(link.access_token))
        except Exception as error:  # closing the account mustn't fail because a bank didn't answer
            logger.info("Plaid item removal for %s didn't complete: %s", link.id, error)
        db.query(BankLinkAccount).filter(BankLinkAccount.link_id == link.id).delete()
        db.query(BankTransfer).filter(BankTransfer.link_id == link.id).update({BankTransfer.link_id: None})
        db.delete(link)


@router.get("/webhook")
async def webhook_status():
    return {"configured": bool(get_settings().plaid_webhook_url)}


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    """Plaid's nudge that something changed. Nothing in the body is trusted: details are fetched from Plaid."""
    try:
        body = await request.json()
    except ValueError:
        body = {}
    kind = str((body or {}).get("webhook_type") or "")
    try:
        plaid = get_gateway()
    except HTTPException:
        return {"received": True}
    try:
        if kind == "TRANSFER":
            sync_events(db, plaid)
        elif kind == "ITEM":
            link = db.query(BankLink).filter(BankLink.item_id == str(body.get("item_id") or "")).first()
            if link is not None:
                item = plaid.item(unseal(link.access_token))
                if item["error_code"] == "ITEM_LOGIN_REQUIRED":
                    link.status, link.error_code = "needs_update", item["error_code"]
                elif item["error_code"]:
                    link.status, link.error_code = "error", item["error_code"]
                else:
                    link.status, link.error_code = "active", None
                db.commit()
    except PlaidError as error:
        db.rollback()
        logger.warning("Plaid webhook follow-up failed: %s", error.code)
        # A 5xx makes Plaid try again later
        raise HTTPException(status_code=502, detail="Retry later")
    return {"received": True}


# ---------- Routes: transfers ----------

@router.post("/transfers/deposit")
async def deposit_from_bank(payload: TransferRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return start_transfer(db, user_id, payload, "deposit")


@router.post("/transfers/withdraw")
async def withdraw_to_bank(payload: TransferRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return start_transfer(db, user_id, payload, "withdrawal")


@router.get("/transfers/history")
async def transfer_history(limit: int = Query(50, ge=1, le=200), user_id: str = Depends(get_current_user_id),
                           db: Session = Depends(get_db)):
    if db.query(BankTransfer.id).filter(BankTransfer.user_id == user_id, BankTransfer.undone.is_(False),
                                        BankTransfer.status.in_(["pending", "posted"])).first():
        sync_quietly(db)
    transfers = (db.query(BankTransfer).filter(BankTransfer.user_id == user_id)
                 .order_by(BankTransfer.created_at.desc()).limit(limit).all())
    return {"transfers": [show_transfer(t) for t in transfers]}


@router.post("/transfers/sync")
async def sync_transfers(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    sync_quietly(db)
    return {"synced": True}


@router.get("/transfers/{transfer_id}/status")
async def transfer_status(transfer_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    sync_quietly(db)
    transfer = db.query(BankTransfer).filter(BankTransfer.id == transfer_id, BankTransfer.user_id == user_id).first()
    if transfer is None:
        raise HTTPException(status_code=404, detail="That transfer wasn't found")
    return show_transfer(transfer)


@router.post("/transfers/quote")
async def beneficiary_quote(user_id: str = Depends(get_current_user_id)):
    raise HTTPException(status_code=503, detail=NOT_YET)


@router.post("/transfers/initiate")
async def beneficiary_send(user_id: str = Depends(get_current_user_id)):
    raise HTTPException(status_code=503, detail=NOT_YET)


@router.post("/sandbox/simulate")
async def sandbox_simulate(payload: SimulateRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Plaid sandbox only: move a test transfer along to try the whole flow."""
    if is_production() or get_settings().plaid_env == "production":
        raise HTTPException(status_code=404, detail="Not found")
    if payload.event not in SANDBOX_EVENTS:
        raise HTTPException(status_code=400, detail=f"Use one of: {', '.join(sorted(SANDBOX_EVENTS))}")
    transfer = db.query(BankTransfer).filter(BankTransfer.id == payload.transfer_id, BankTransfer.user_id == user_id).first()
    if transfer is None or not transfer.plaid_transfer_id:
        raise HTTPException(status_code=404, detail="That transfer wasn't found")
    plaid = get_gateway()
    try:
        plaid.simulate(transfer.plaid_transfer_id, payload.event)
        sync_events(db, plaid)
    except PlaidError as error:
        db.rollback()
        raise plaid_failed(error, "sandbox simulate")
    db.refresh(transfer)
    return show_transfer(transfer)
