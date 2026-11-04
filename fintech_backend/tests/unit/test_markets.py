"""
Crypto and ETF orders: cash moves, positions change, and the server sets the price.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_markets.py --noconftest --import-mode=importlib
"""

import os
from decimal import Decimal

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import markets
from app.auth.dependencies import get_current_user_id
from app.database import market_models  # noqa: F401 - registers the tables
from app.database.config import Base, get_db
from app.database.market_models import MarketPosition
from app.database.models import Account, AccountTypeEnum, Transaction, TransactionTypeEnum, User
from app.services import market_quotes

PRICES = {("crypto", "BTC"): Decimal("50000"), ("etf", "SPY"): Decimal("500")}


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(User(id="ada", email="ada@example.com", password_hash="x", first_name="Ada", last_name="Test"))
        db.add(Account(id="acct-ada", user_id="ada", account_number="ACCTADA0000001", account_name="Cash",
                       account_type=AccountTypeEnum.CHECKING, currency="USD", is_primary=True,
                       current_balance=Decimal("1000"), available_balance=Decimal("1000")))
        db.commit()

    async def price_for(asset_type, symbol):
        return PRICES[(asset_type, symbol)]

    async def prices_for(pairs):
        return {pair: PRICES.get(pair) for pair in pairs}

    monkeypatch.setattr(market_quotes, "price_for", price_for)
    monkeypatch.setattr(market_quotes, "prices_for", prices_for)
    monkeypatch.setenv("ENABLE_MARKET_TRADING", "true")

    app = FastAPI()
    app.include_router(markets.router, prefix="/api/v1")

    def session():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user_id] = lambda: "ada"
    return TestClient(app), Session


def order(client, **body):
    return client.post("/api/v1/markets/orders", json=body)


def test_buying_spends_cash_at_the_server_price(env):
    client, Session = env
    result = order(client, asset_type="crypto", symbol="btc", side="buy", amount="250")
    assert result.status_code == 201
    data = result.json()["data"]
    assert data["quantity"] == pytest.approx(0.005)
    assert data["cash_available"] == 750

    with Session() as db:
        position = db.query(MarketPosition).one()
        assert position.quantity == Decimal("0.005")
        assert position.cost_basis == Decimal("250.00")
        assert db.query(Transaction).one().transaction_type == TransactionTypeEnum.INVESTMENT

    held = client.get("/api/v1/markets/positions").json()
    assert held["data"][0]["value"] == 250
    assert held["data"][0]["gain"] == 0


def test_selling_returns_cash_and_shrinks_the_position(env):
    client, Session = env
    order(client, asset_type="etf", symbol="SPY", side="buy", amount="500")
    PRICES[("etf", "SPY")] = Decimal("600")
    try:
        half = order(client, asset_type="etf", symbol="SPY", side="sell", amount="300").json()["data"]
        assert half["quantity"] == pytest.approx(0.5)
        assert half["cash_available"] == 800
        rest = order(client, asset_type="etf", symbol="SPY", side="sell", sell_all=True).json()["data"]
        assert rest["position_quantity"] == 0
        assert rest["cash_available"] == 1100
    finally:
        PRICES[("etf", "SPY")] = Decimal("500")
    with Session() as db:
        assert db.get(Account, "acct-ada").available_balance == Decimal("1100.00")
        assert db.query(MarketPosition).one().cost_basis == Decimal("0")


def test_order_limits(env):
    client, _ = env
    assert order(client, asset_type="crypto", symbol="BTC", side="buy", amount="5000").status_code == 402
    assert order(client, asset_type="crypto", symbol="BTC", side="buy", amount="0.5").status_code == 400
    assert order(client, asset_type="crypto", symbol="FAKE", side="buy", amount="10").status_code == 404
    assert order(client, asset_type="crypto", symbol="BTC", side="sell", amount="10").status_code == 400


def test_orders_stay_off_until_trading_is_switched_on(env, monkeypatch):
    client, Session = env
    monkeypatch.setenv("ENABLE_MARKET_TRADING", "false")
    blocked = order(client, asset_type="crypto", symbol="BTC", side="buy", amount="100")
    assert blocked.status_code == 503
    with Session() as db:
        assert db.get(Account, "acct-ada").available_balance == Decimal("1000.00")
