"""
Crypto and ETF markets: live quotes, charts, positions and orders.

With Alpaca set up (ALPACA_* settings), orders go to the customer's own brokerage account
at Alpaca and holdings come from there (brokerage.py). Without it, development can still try
orders on Hoardrun's own books with ENABLE_MARKET_TRADING=true; production never does that.
"""

import os
import uuid
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...auth.dependencies import get_current_user_id
from ...database.config import get_db
from ...database.market_models import MarketOrder, MarketPosition
from ...database.models import (
    Account, PaymentMethodEnum, Transaction, TransactionDirectionEnum, TransactionStatusEnum, TransactionTypeEnum,
)
from ...auth.signing_key import is_production
from ...services import alpaca, market_quotes
from ...services.deposit_ledger import cash_account
from . import brokerage
from .venture import cash_accounts, cash_balance

router = APIRouter(prefix="/markets", tags=["markets"])

AssetType = Literal["crypto", "etf"]
QUANTUM = Decimal("0.00000001")
CENT = Decimal("0.01")


def internal_books() -> bool:
    """Orders on Hoardrun's own books: a development stand-in for a broker, never in production."""
    return os.getenv("ENABLE_MARKET_TRADING", "").lower() == "true" and not is_production() and not alpaca.configured()


def trading_enabled() -> bool:
    return alpaca.configured() or internal_books()


def known(asset_type: str, symbol: str) -> bool:
    return symbol in (market_quotes.CRYPTO_NAMES if asset_type == "crypto" else market_quotes.ETF_INFO)


def asset_name(asset_type: str, symbol: str) -> str:
    return market_quotes.CRYPTO_NAMES.get(symbol, symbol) if asset_type == "crypto" else market_quotes.ETF_INFO.get(symbol, (symbol,))[0]


class OrderCreate(BaseModel):
    asset_type: AssetType
    symbol: str = Field(min_length=1, max_length=12)
    side: Literal["buy", "sell"]
    amount: Optional[Decimal] = Field(default=None, gt=0, le=Decimal("1000000"))
    sell_all: bool = False


@router.get("/catalog")
async def catalog(_: str = Depends(get_current_user_id)):
    return {
        "crypto": [{"symbol": symbol, "name": name} for symbol, name in market_quotes.CRYPTO],
        "etfs": [{"symbol": symbol, "name": name, "about": about} for symbol, name, about in market_quotes.ETFS],
        "trading_enabled": trading_enabled(),
    }


@router.get("/etfs")
async def etfs(_: str = Depends(get_current_user_id)):
    try:
        quotes = await market_quotes.etf_quotes()
    except market_quotes.QuoteUnavailable as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))
    return {"data": quotes, "trading_enabled": trading_enabled()}


@router.get("/etfs/{symbol}/chart")
async def etf_chart(symbol: str, range: str = Query(default="1M"), _: str = Depends(get_current_user_id)):
    symbol = symbol.upper()
    if symbol not in market_quotes.ETF_INFO:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown ETF")
    try:
        points = await market_quotes.etf_history(symbol, range.upper())
    except market_quotes.QuoteUnavailable as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))
    return {"data": points}


@router.get("/positions")
async def positions(asset_type: Optional[AssetType] = None, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    if alpaca.configured():
        # Holdings live at Alpaca; this also sweeps sale proceeds back into Hoardrun cash
        rows = brokerage.reconcile(db, user_id) or []
        data = [{**row, "name": asset_name(row["asset_type"], row["symbol"])} for row in rows
                if asset_type is None or row["asset_type"] == asset_type]
        account = brokerage.show(db.get(brokerage.BrokerageAccount, user_id))
        return {"data": data, "cash_available": float(cash_balance(db, user_id)), "trading_enabled": account["state"] == "open",
                "brokerage": account}
    query = db.query(MarketPosition).filter(MarketPosition.user_id == user_id, MarketPosition.quantity > 0)
    if asset_type:
        query = query.filter(MarketPosition.asset_type == asset_type)
    rows = query.all()
    prices = await market_quotes.prices_for([(row.asset_type, row.symbol) for row in rows])
    data = []
    for row in rows:
        price = prices.get((row.asset_type, row.symbol))
        quantity = Decimal(row.quantity)
        value = (quantity * price).quantize(CENT) if price is not None else None
        cost = Decimal(row.cost_basis)
        data.append({
            "asset_type": row.asset_type,
            "symbol": row.symbol,
            "name": asset_name(row.asset_type, row.symbol),
            "quantity": float(quantity),
            "cost_basis": float(cost),
            "price": float(price) if price is not None else None,
            "value": float(value) if value is not None else None,
            "gain": float(value - cost) if value is not None else None,
        })
    return {"data": data, "cash_available": float(cash_balance(db, user_id)), "trading_enabled": trading_enabled()}


@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def place_order(payload: OrderCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    if not trading_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trading isn't switched on yet. Hoardrun needs a licensed broker or exchange connected before orders can be placed.",
        )
    symbol = payload.symbol.upper()
    if not known(payload.asset_type, symbol):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown asset")
    if not payload.sell_all and payload.amount is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter an amount")
    if alpaca.configured():
        name = asset_name(payload.asset_type, symbol)
        if payload.side == "buy":
            result = brokerage.buy(db, user_id, payload.asset_type, symbol, name, payload.amount or Decimal(0))
        else:
            result = brokerage.sell(db, user_id, payload.asset_type, symbol, name, payload.amount, payload.sell_all)
        return {"data": {**result, "cash_available": float(cash_balance(db, user_id))}}

    try:
        price = await market_quotes.price_for(payload.asset_type, symbol)
    except market_quotes.QuoteUnavailable as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))

    position = (
        db.query(MarketPosition)
        .filter_by(user_id=user_id, asset_type=payload.asset_type, symbol=symbol)
        .with_for_update()
        .first()
    )
    now = datetime.now(timezone.utc)
    name = asset_name(payload.asset_type, symbol)

    if payload.side == "buy":
        amount = (payload.amount or Decimal(0)).quantize(CENT)
        if amount < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The smallest order is $1")
        quantity = (amount / price).quantize(QUANTUM, rounding=ROUND_DOWN)
        account = (
            cash_accounts(db, user_id).filter(Account.available_balance >= amount)
            .order_by(Account.is_primary.desc(), Account.available_balance.desc()).with_for_update().first()
        )
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Not enough cash. This order is ${amount:,.2f} and your Hoardrun cash is ${cash_balance(db, user_id):,.2f}. Add money first.",
            )
        account.available_balance = Decimal(account.available_balance) - amount
        account.current_balance = Decimal(account.current_balance) - amount
        if position is None:
            position = MarketPosition(id=str(uuid.uuid4()), user_id=user_id, asset_type=payload.asset_type, symbol=symbol, quantity=0, cost_basis=0)
            db.add(position)
        position.quantity = Decimal(position.quantity or 0) + quantity
        position.cost_basis = Decimal(position.cost_basis or 0) + amount
        kind, direction, description = TransactionTypeEnum.INVESTMENT, TransactionDirectionEnum.OUTBOUND, f"Bought {quantity.normalize()} {symbol}"
    else:
        held = Decimal(position.quantity) if position else Decimal(0)
        if held <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"You don't hold any {name}")
        quantity = held if payload.sell_all else ((payload.amount or Decimal(0)) / price).quantize(QUANTUM, rounding=ROUND_DOWN)
        if quantity > held:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"You hold {held.normalize()} {symbol}, worth ${(held * price).quantize(CENT):,.2f}")
        amount = (quantity * price).quantize(CENT, rounding=ROUND_DOWN)
        if amount < CENT:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That's too small to sell")
        cost_share = (Decimal(position.cost_basis) * quantity / held).quantize(CENT)
        position.quantity = held - quantity
        position.cost_basis = Decimal(position.cost_basis) - cost_share if position.quantity > 0 else Decimal(0)
        account = cash_account(db, user_id, "USD")
        account.available_balance = Decimal(account.available_balance) + amount
        account.current_balance = Decimal(account.current_balance) + amount
        kind, direction, description = TransactionTypeEnum.SALE, TransactionDirectionEnum.INBOUND, f"Sold {quantity.normalize()} {symbol}"

    transaction = Transaction(
        id=str(uuid.uuid4()), user_id=user_id, account_id=account.id, transaction_type=kind,
        status=TransactionStatusEnum.COMPLETED, direction=direction, amount=amount, currency="USD",
        description=description, merchant_name=name, payment_method=PaymentMethodEnum.OTHER,
        reference_number=f"MK-{uuid.uuid4().hex[:12].upper()}", transaction_date=now, posted_date=now,
        balance_after=account.current_balance,
    )
    db.add(transaction)
    db.add(MarketOrder(
        id=str(uuid.uuid4()), user_id=user_id, asset_type=payload.asset_type, symbol=symbol, side=payload.side,
        quantity=quantity, price=price, amount=amount, transaction_id=transaction.id,
    ))
    db.commit()
    return {
        "data": {
            "side": payload.side,
            "symbol": symbol,
            "name": name,
            "quantity": float(quantity),
            "price": float(price),
            "amount": float(amount),
            "reference": transaction.reference_number,
            "position_quantity": float(position.quantity),
            "cash_available": float(cash_balance(db, user_id)),
        }
    }
