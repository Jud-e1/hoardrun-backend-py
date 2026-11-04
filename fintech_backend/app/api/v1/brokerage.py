"""
Investing through Alpaca: a brokerage account per customer, funded from Hoardrun cash.

- Opening: date of birth, SSN, address, employment and the FINRA disclosures go to Alpaca,
  which runs its own checks. The SSN is passed through and never stored or logged here.
- Buying: the amount leaves Hoardrun cash and is journaled from Hoardrun's firm account into
  the customer's account at Alpaca, then a fractional market order is placed. If the order
  can't be placed, the journal is reversed and the cash comes straight back.
- Selling: an order at Alpaca. Proceeds, and any cash a buy didn't use, are swept back into
  Hoardrun cash once Alpaca says they can be withdrawn (sweep()).
- Holdings are Alpaca's; they're mirrored into market_positions so net worth stays right.
"""

import logging
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, DECIMAL, ForeignKey, String
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...database.config import Base, get_db
from ...database.market_models import MarketPosition
from ...database.models import (
    Account, AccountStatusEnum, MerchantCategoryEnum, PaymentMethodEnum, Transaction, TransactionDirectionEnum,
    TransactionStatusEnum, TransactionTypeEnum, User,
)
from ...services import alpaca
from ...services.deposit_ledger import cash_account
from ...services.inbox import notify
from .identity import require_verified_identity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/markets/brokerage", tags=["markets"])

CENT = Decimal("0.01")
MIN_ORDER = Decimal("1")
MAX_ORDER = Decimal("25000")
OPEN_STATES = {"ACTIVE", "APPROVED"}
FINISHED = {"filled", "canceled", "expired", "rejected", "done_for_day"}
STATES = re.compile(r"^[A-Z]{2}$")


class BrokerageAccount(Base):
    """A customer's account at Alpaca, and the cash there that isn't invested."""
    __tablename__ = "brokerage_accounts"

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    alpaca_account_id = Column(String(60), unique=True, nullable=False)
    status = Column(String(30), nullable=False, default="SUBMITTED")
    uninvested_cash = Column(DECIMAL(18, 2), nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class BrokerOrder(Base):
    """An order placed at Alpaca for a customer."""
    __tablename__ = "broker_orders"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    alpaca_order_id = Column(String(60), unique=True)
    asset_type = Column(String(8), nullable=False)
    symbol = Column(String(12), nullable=False)
    side = Column(String(4), nullable=False)
    notional = Column(DECIMAL(18, 2))
    status = Column(String(20), nullable=False, default="new")
    filled_qty = Column(DECIMAL(28, 10))
    filled_avg_price = Column(DECIMAL(18, 8))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Address(BaseModel):
    line1: str = Field(min_length=3, max_length=120)
    line2: Optional[str] = Field(None, max_length=120)
    city: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=2, max_length=2)
    postal_code: str = Field(pattern=r"^\d{5}(-\d{4})?$")


class Disclosures(BaseModel):
    is_control_person: bool = False
    is_affiliated_exchange_or_finra: bool = False
    is_politically_exposed: bool = False
    immediate_family_exposed: bool = False


class OpenRequest(BaseModel):
    date_of_birth: date
    ssn: str = Field(min_length=9, max_length=11)
    phone: str = Field(min_length=10, max_length=20)
    address: Address
    employment_status: Literal["employed", "unemployed", "student", "retired"]
    funding_source: Literal["employment_income", "investments", "inheritance", "business_income", "savings", "family"] = "employment_income"
    disclosures: Disclosures = Disclosures()
    accept_agreements: bool = False


# ---------- Helpers ----------

def broker_failed(error: alpaca.AlpacaError, what: str) -> HTTPException:
    logger.warning("Alpaca %s failed (%s)", what, error.status)
    # 401 is a bad key; Alpaca also uses 403 for ordinary rejections (not tradable, buying power)
    if error.status == 401:
        return HTTPException(status_code=503, detail="Investing isn't available right now.")
    return HTTPException(status_code=502, detail=f"The broker didn't accept that: {error}" if str(error) else "The broker didn't accept that. Try again.")


def clean_ssn(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 9 or digits.startswith(("000", "666", "9")) or digits[3:5] == "00" or digits[5:] == "0000":
        raise HTTPException(status_code=400, detail="That doesn't look like a valid SSN.")
    return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"


def age_on(today: date, born: date) -> int:
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def open_account_for(db: Session, user_id: str) -> BrokerageAccount:
    """The customer's Alpaca account, if Alpaca has approved it; otherwise say what's missing."""
    if not alpaca.configured():
        raise HTTPException(status_code=503, detail="Investing isn't set up yet")
    account = db.get(BrokerageAccount, user_id)
    if account is None:
        raise HTTPException(status_code=409, detail="Open your investing account first. It takes a few minutes.")
    if account.status not in OPEN_STATES:
        refresh_status(db, account)
    if account.status not in OPEN_STATES:
        raise HTTPException(status_code=409, detail="Your investing account is still being approved. We'll email you when it's ready.")
    return account


def refresh_status(db: Session, account: BrokerageAccount) -> None:
    try:
        status = str(alpaca.get_broker().account(account.alpaca_account_id).get("status") or account.status)
    except alpaca.AlpacaError:
        return
    if status != account.status:
        before, account.status, account.updated_at = account.status, status, datetime.utcnow()
        if status in OPEN_STATES and before not in OPEN_STATES:
            notify(db, account.user_id, "success", "Your investing account is open",
                   "You can now buy ETFs and crypto with your Hoardrun cash.", link="/etfs",
                   key=f"brokerage-open:{account.alpaca_account_id}", email=True)
        elif status == "REJECTED":
            notify(db, account.user_id, "warning", "We couldn't open your investing account",
                   "Our broker couldn't approve the account. Contact support and we'll help.", link="/help",
                   key=f"brokerage-rejected:{account.alpaca_account_id}", email=True)
        db.commit()


def ledger(db: Session, user_id: str, account: Account, amount: Decimal, kind: TransactionTypeEnum,
           direction: TransactionDirectionEnum, description: str, merchant: str, prefix: str) -> Transaction:
    now = datetime.now(timezone.utc)
    entry = Transaction(
        id=str(uuid.uuid4()), user_id=user_id, account_id=account.id, transaction_type=kind, direction=direction,
        status=TransactionStatusEnum.COMPLETED, amount=amount, currency="USD", payment_method=PaymentMethodEnum.OTHER,
        description=description, merchant_name=merchant, merchant_category=MerchantCategoryEnum.INVESTMENT_TRADE,
        reference_number=f"{prefix}-{uuid.uuid4().hex[:16].upper()}", transaction_date=now, posted_date=now,
        balance_after=account.current_balance,
    )
    db.add(entry)
    return entry


# ---------- Orders ----------

def buy(db: Session, user_id: str, asset_type: str, symbol: str, name: str, amount: Decimal) -> dict:
    account = open_account_for(db, user_id)
    amount = amount.quantize(CENT)
    if not MIN_ORDER <= amount <= MAX_ORDER:
        raise HTTPException(status_code=400, detail=f"Orders are ${MIN_ORDER:,.0f} to ${MAX_ORDER:,.0f}.")
    cash = (
        db.query(Account).filter(Account.user_id == user_id, Account.currency == "USD", Account.status == AccountStatusEnum.ACTIVE,
                                 Account.available_balance >= amount)
        .order_by(Account.is_primary.desc(), Account.available_balance.desc()).with_for_update().first()
    )
    if cash is None:
        raise HTTPException(status_code=402, detail=f"Not enough cash. This order is ${amount:,.2f}. Add money first.")
    broker = alpaca.get_broker()
    try:
        broker.journal(broker.firm, account.alpaca_account_id, amount, f"Buy {symbol}")
    except alpaca.AlpacaError as error:
        db.rollback()
        raise broker_failed(error, "journal in")
    order_id = str(uuid.uuid4())
    try:
        placed = broker.order(account.alpaca_account_id, asset_type=asset_type, symbol=symbol, side="buy", notional=amount, client_id=order_id)
    except alpaca.AlpacaError as error:
        # The cash went over but the order didn't: bring it straight back
        try:
            broker.journal(account.alpaca_account_id, broker.firm, amount, f"Return {symbol}")
        except alpaca.AlpacaError:
            logger.error("Couldn't return $%s from %s after a failed order; the sweep will", amount, account.alpaca_account_id)
            account.uninvested_cash = Decimal(account.uninvested_cash or 0) + amount
            cash.available_balance = Decimal(cash.available_balance) - amount
            cash.current_balance = Decimal(cash.current_balance) - amount
            ledger(db, user_id, cash, amount, TransactionTypeEnum.TRANSFER_OUT, TransactionDirectionEnum.OUTBOUND,
                   f"To your investing account (order for {symbol} failed)", "Hoardrun Invest", "BK")
            db.commit()
        raise broker_failed(error, "order")
    cash.available_balance = Decimal(cash.available_balance) - amount
    cash.current_balance = Decimal(cash.current_balance) - amount
    # Counted at Alpaca until the next sync turns it into a holding
    account.uninvested_cash = Decimal(account.uninvested_cash or 0) + amount
    entry = ledger(db, user_id, cash, amount, TransactionTypeEnum.INVESTMENT, TransactionDirectionEnum.OUTBOUND,
                   f"Buy {name}", name, "BK")
    db.add(BrokerOrder(id=order_id, user_id=user_id, alpaca_order_id=placed.get("id"), asset_type=asset_type, symbol=symbol,
                       side="buy", notional=amount, status=str(placed.get("status") or "new")))
    db.commit()
    return {"side": "buy", "symbol": symbol, "name": name, "amount": float(amount), "status": placed.get("status"),
            "reference": entry.reference_number, "placed_at_broker": True}


def sell(db: Session, user_id: str, asset_type: str, symbol: str, name: str, amount: Optional[Decimal], sell_all: bool) -> dict:
    account = open_account_for(db, user_id)
    broker = alpaca.get_broker()
    order_id = str(uuid.uuid4())
    try:
        if sell_all:
            placed = broker.close_position(account.alpaca_account_id, asset_type=asset_type, symbol=symbol)
        else:
            amount = (amount or Decimal(0)).quantize(CENT)
            if amount < MIN_ORDER:
                raise HTTPException(status_code=400, detail="The smallest sale is $1.")
            placed = broker.order(account.alpaca_account_id, asset_type=asset_type, symbol=symbol, side="sell", notional=amount, client_id=order_id)
    except alpaca.AlpacaError as error:
        raise broker_failed(error, "sell")
    db.add(BrokerOrder(id=order_id, user_id=user_id, alpaca_order_id=placed.get("id"), asset_type=asset_type, symbol=symbol,
                       side="sell", notional=None if sell_all else amount, status=str(placed.get("status") or "new")))
    db.commit()
    return {"side": "sell", "symbol": symbol, "name": name, "amount": float(amount) if amount and not sell_all else None,
            "status": placed.get("status"), "placed_at_broker": True}


# ---------- Keeping Hoardrun in step with Alpaca ----------

def sync_orders(db: Session, account: BrokerageAccount) -> None:
    broker = alpaca.get_broker()
    for order in db.query(BrokerOrder).filter(BrokerOrder.user_id == account.user_id, BrokerOrder.status.notin_(FINISHED)).all():
        if not order.alpaca_order_id:
            continue
        try:
            latest = broker.get_order(account.alpaca_account_id, order.alpaca_order_id)
        except alpaca.AlpacaError:
            continue
        order.status = str(latest.get("status") or order.status)
        if latest.get("filled_qty") is not None:
            order.filled_qty = Decimal(str(latest["filled_qty"]))
        if latest.get("filled_avg_price") is not None:
            order.filled_avg_price = Decimal(str(latest["filled_avg_price"]))
        order.updated_at = datetime.utcnow()


def sweep(db: Session, account: BrokerageAccount) -> Decimal:
    """Bring withdrawable cash at Alpaca (sale proceeds, unused buy money) back into Hoardrun cash."""
    broker = alpaca.get_broker()
    try:
        trading = broker.trading_account(account.alpaca_account_id)
    except alpaca.AlpacaError:
        return Decimal(0)
    withdrawable = Decimal(str(trading.get("cash_withdrawable") or 0)).quantize(CENT)
    total = Decimal(str(trading.get("cash") or 0)).quantize(CENT)
    if withdrawable >= CENT:
        try:
            broker.journal(account.alpaca_account_id, broker.firm, withdrawable, "To Hoardrun cash")
        except alpaca.AlpacaError:
            account.uninvested_cash = max(total, Decimal(0))
            return Decimal(0)
        cash = cash_account(db, account.user_id, "USD")
        cash.available_balance = Decimal(cash.available_balance) + withdrawable
        cash.current_balance = Decimal(cash.current_balance) + withdrawable
        ledger(db, account.user_id, cash, withdrawable, TransactionTypeEnum.SALE, TransactionDirectionEnum.INBOUND,
               "From your investing account", "Hoardrun Invest", "BK")
        notify(db, account.user_id, "transaction", "Money from investing",
               f"${withdrawable:,.2f} from your investing account is back in your Hoardrun cash.", link="/transactions",
               key=f"sweep:{account.alpaca_account_id}:{datetime.utcnow().isoformat()}", email=True)
        total -= withdrawable
    account.uninvested_cash = max(total, Decimal(0))
    return withdrawable


def mirror_positions(db: Session, account: BrokerageAccount) -> list:
    """Alpaca's positions, copied into market_positions so net worth and other pages see them."""
    try:
        held = alpaca.get_broker().positions(account.alpaca_account_id)
    except alpaca.AlpacaError:
        return []
    db.query(MarketPosition).filter(MarketPosition.user_id == account.user_id).delete(synchronize_session=False)
    rows = []
    for position in held:
        crypto = position.get("asset_class") == "crypto"
        symbol = str(position.get("symbol") or "")
        symbol = symbol[:-3] if crypto and symbol.endswith("USD") else symbol.replace("/USD", "")
        quantity = Decimal(str(position.get("qty") or 0))
        if quantity <= 0:
            continue
        db.add(MarketPosition(id=str(uuid.uuid4()), user_id=account.user_id, asset_type="crypto" if crypto else "etf",
                              symbol=symbol, quantity=quantity, cost_basis=Decimal(str(position.get("cost_basis") or 0)).quantize(CENT)))
        rows.append({"asset_type": "crypto" if crypto else "etf", "symbol": symbol, "quantity": float(quantity),
                     "cost_basis": float(Decimal(str(position.get("cost_basis") or 0))),
                     "price": float(position["current_price"]) if position.get("current_price") is not None else None,
                     "value": float(position["market_value"]) if position.get("market_value") is not None else None,
                     "gain": float(position["unrealized_pl"]) if position.get("unrealized_pl") is not None else None})
    return rows


def reconcile(db: Session, user_id: str) -> Optional[list]:
    """Orders, cash and holdings brought up to date from Alpaca. None when there's no open account."""
    if not alpaca.configured():
        return None
    account = db.get(BrokerageAccount, user_id)
    if account is None:
        return None
    if account.status not in OPEN_STATES:
        refresh_status(db, account)
        if account.status not in OPEN_STATES:
            return None
    sync_orders(db, account)
    sweep(db, account)
    rows = mirror_positions(db, account)
    account.updated_at = datetime.utcnow()
    db.commit()
    return rows


def show(account: Optional[BrokerageAccount]) -> dict:
    status = account.status if account else None
    return {"configured": alpaca.configured(), "status": status,
            "state": "none" if account is None else "open" if status in OPEN_STATES else "rejected" if status == "REJECTED"
            else "action_required" if status == "ACTION_REQUIRED" else "pending",
            "uninvested_cash": float(account.uninvested_cash or 0) if account else 0}


# ---------- Routes ----------

@router.get("")
async def status(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    account = db.get(BrokerageAccount, user_id)
    if account is not None and account.status not in OPEN_STATES and alpaca.configured():
        refresh_status(db, account)
    return show(account)


@router.post("/open")
async def open_account(payload: OpenRequest, request: Request, user_id: str = Depends(get_current_user_id),
                       db: Session = Depends(get_db)):
    if not alpaca.configured():
        raise HTTPException(status_code=503, detail="Investing isn't set up yet")
    require_verified_identity(db, user_id, "open an investing account")
    if db.get(BrokerageAccount, user_id) is not None:
        raise HTTPException(status_code=409, detail="You already have an investing account.")
    if not payload.accept_agreements:
        raise HTTPException(status_code=400, detail="Agree to the account agreements to open an account.")
    if age_on(date.today(), payload.date_of_birth) < 18:
        raise HTTPException(status_code=400, detail="You need to be 18 or older to invest.")
    if not STATES.match(payload.address.state.upper()):
        raise HTTPException(status_code=400, detail="Use a US state, like CA or NY.")
    ssn = clean_ssn(payload.ssn)
    user = db.get(User, user_id)
    signed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ip = request.client.host if request.client else "127.0.0.1"
    street = [payload.address.line1.strip()] + ([payload.address.line2.strip()] if payload.address.line2 else [])
    body = {
        "contact": {"email_address": user.email, "phone_number": payload.phone, "street_address": street,
                    "city": payload.address.city.strip(), "state": payload.address.state.upper(), "postal_code": payload.address.postal_code},
        "identity": {"given_name": user.first_name, "family_name": user.last_name, "date_of_birth": payload.date_of_birth.isoformat(),
                     "tax_id": ssn, "tax_id_type": "USA_SSN", "country_of_citizenship": "USA", "country_of_birth": "USA",
                     "country_of_tax_residence": "USA", "funding_source": [payload.funding_source]},
        "disclosures": {**payload.disclosures.dict(), "employment_status": payload.employment_status},
        "agreements": [{"agreement": name, "signed_at": signed, "ip_address": ip}
                       for name in ("customer_agreement", "account_agreement", "crypto_agreement")],
        "enabled_assets": ["us_equity", "crypto"],
    }
    try:
        created = alpaca.get_broker().create_account(body)
    except alpaca.AlpacaError as error:
        raise broker_failed(error, "account open")
    finally:
        del body, ssn
    account = BrokerageAccount(user_id=user_id, alpaca_account_id=created["id"], status=str(created.get("status") or "SUBMITTED"))
    db.add(account)
    notify(db, user_id, "security", "Investing account requested",
           "We've sent your details to our broker, Alpaca, to open your investing account. If this wasn't you, contact support.",
           link="/etfs", key=f"brokerage-requested:{created['id']}")
    db.commit()
    return show(account)


@router.post("/sync")
async def sync(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    reconcile(db, user_id)
    return show(db.get(BrokerageAccount, user_id))
