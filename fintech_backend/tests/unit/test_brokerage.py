"""
Investing through Alpaca. Alpaca is faked; Hoardrun's ledger, accounts and routes are real.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_brokerage.py --noconftest --import-mode=importlib
"""

import asyncio
import logging
import os
from datetime import date
from decimal import Decimal

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import brokerage, identity, markets
from app.api.v1 import savings_store  # noqa: F401 - net worth reads its tables
from app.auth.dependencies import get_current_user_id
from app.database.config import Base, get_db
from app.database.market_models import MarketPosition
from app.database.models import Account, Transaction, User
from app.services import alpaca, email_service, market_quotes
from app.services.deposit_ledger import cash_account
from app.services.wealth import wealth

FIRM = "firm-account-1"
SSN = "123-45-6789"
OPEN = {
    "date_of_birth": "1990-04-02", "ssn": SSN, "phone": "+14155550100",
    "address": {"line1": "1 Market St", "city": "San Francisco", "state": "CA", "postal_code": "94105"},
    "employment_status": "employed", "accept_agreements": True,
}


class FakeAlpaca:
    firm = FIRM

    def __init__(self):
        self.accounts, self.journals, self.orders, self.closed = [], [], [], []
        self.status = "SUBMITTED"
        self.held = []
        self.cash = Decimal("0")
        self.withdrawable = Decimal("0")
        self.fail_order = False
        self.fail_return = False

    def create_account(self, payload):
        self.accounts.append(payload)
        return {"id": "acct-ada", "status": self.status}

    def account(self, account_id):
        return {"id": account_id, "status": self.status}

    def trading_account(self, account_id):
        return {"cash": str(self.cash), "cash_withdrawable": str(self.withdrawable)}

    def journal(self, from_account, to_account, amount, description):
        if self.fail_return and from_account != FIRM:
            raise alpaca.AlpacaError(422, "insufficient withdrawable cash")
        self.journals.append((from_account, to_account, amount))
        if from_account == FIRM:
            self.cash += amount
        else:
            self.cash -= amount
            self.withdrawable -= amount
        return {"id": f"j{len(self.journals)}", "status": "executed"}

    def order(self, account_id, *, asset_type, symbol, side, notional, client_id):
        if self.fail_order:
            raise alpaca.AlpacaError(403, "asset is not tradable")
        self.orders.append({"symbol": alpaca.broker_symbol(asset_type, symbol), "side": side, "notional": notional})
        return {"id": f"ord-{len(self.orders)}", "status": "accepted"}

    def close_position(self, account_id, *, asset_type, symbol):
        self.closed.append(alpaca.position_symbol(asset_type, symbol))
        return {"id": "ord-close", "status": "accepted"}

    def get_order(self, account_id, order_id):
        return {"id": order_id, "status": "filled", "filled_qty": "0.1", "filled_avg_price": "500"}

    def positions(self, account_id):
        return self.held

    def snapshots(self, symbols):
        return {s: {"latestTrade": {"p": 512.5, "t": "2026-11-04T15:00:00Z"}, "prevDailyBar": {"c": 500},
                    "dailyBar": {"o": 501, "h": 515, "l": 499, "c": 512.5}} for s in symbols}

    def bars(self, symbol, span):
        return [{"t": "2026-11-03T00:00:00Z", "c": 500.0}, {"t": "2026-11-04T00:00:00Z", "c": 512.5}]


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(User(id="ada", email="ada@example.com", password_hash="x", first_name="Ada", last_name="Mensah", status="active"))
        db.commit()
        account = cash_account(db, "ada", "USD")
        account.available_balance = account.current_balance = Decimal("100")
        db.commit()

    settings = alpaca.get_settings()
    monkeypatch.setattr(settings, "alpaca_broker_key", "key")
    monkeypatch.setattr(settings, "alpaca_broker_secret", "secret")
    monkeypatch.setattr(settings, "alpaca_firm_account_id", FIRM)
    monkeypatch.setattr(settings, "persona_api_key", "")
    fake = FakeAlpaca()
    monkeypatch.setattr(alpaca, "get_broker", lambda: fake)
    monkeypatch.setattr(email_service, "deliver", lambda *a: True)
    monkeypatch.setattr(email_service, "_pool", type("Now", (), {"submit": staticmethod(lambda fn, *a: fn(*a))})())
    market_quotes._etf_cache.clear()

    app = FastAPI()
    app.include_router(brokerage.router, prefix="/api/v1")
    app.include_router(markets.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user_id] = lambda: "ada"
    return TestClient(app), Session, fake


def cash(Session):
    with Session() as db:
        return Decimal(db.query(Account).filter(Account.user_id == "ada").one().available_balance)


def opened(client, fake):
    assert client.post("/api/v1/markets/brokerage/open", json=OPEN).status_code == 200
    fake.status = "ACTIVE"
    assert client.get("/api/v1/markets/brokerage").json()["state"] == "open"


def buy(client, amount, symbol="SPY", kind="etf"):
    return client.post("/api/v1/markets/orders", json={"asset_type": kind, "symbol": symbol, "side": "buy", "amount": amount})


def test_opening_sends_the_details_to_alpaca_and_never_keeps_the_ssn(env, caplog):
    client, Session, fake = env
    with caplog.at_level(logging.DEBUG):
        body = client.post("/api/v1/markets/brokerage/open", json={**OPEN, "ssn": "123456789"}).json()
    assert body["state"] == "pending" and body["status"] == "SUBMITTED"
    sent = fake.accounts[0]
    assert sent["identity"]["tax_id"] == SSN and sent["identity"]["tax_id_type"] == "USA_SSN"
    assert sent["contact"]["street_address"] == ["1 Market St"] and sent["enabled_assets"] == ["us_equity", "crypto"]
    assert {a["agreement"] for a in sent["agreements"]} == {"customer_agreement", "account_agreement", "crypto_agreement"}
    assert sent["disclosures"]["employment_status"] == "employed"
    assert "6789" not in caplog.text and "123456789" not in caplog.text
    # Nowhere in the database
    with Session() as db:
        for table in inspect(db.get_bind()).get_table_names():
            for row in db.execute(text(f'SELECT * FROM "{table}"')).fetchall():
                assert not any(isinstance(v, str) and ("6789" in v and "45" in v) for v in row), table


@pytest.mark.parametrize("change, message", [
    ({"accept_agreements": False}, "Agree to the account agreements"),
    ({"date_of_birth": date.today().replace(year=date.today().year - 17).isoformat()}, "18 or older"),
    ({"ssn": "000-12-3456"}, "valid SSN"),
])
def test_opening_checks_the_basics(env, change, message):
    client, _, fake = env
    response = client.post("/api/v1/markets/brokerage/open", json={**OPEN, **change})
    assert response.status_code == 400 and message in response.json()["detail"] and fake.accounts == []


def test_opening_needs_a_verified_identity_once_checks_are_on(env, monkeypatch):
    client, _, fake = env
    monkeypatch.setattr(identity, "configured", lambda: True)
    assert client.post("/api/v1/markets/brokerage/open", json=OPEN).status_code == 403 and fake.accounts == []


def test_orders_wait_for_an_approved_account(env):
    client, _, fake = env
    assert buy(client, 10).status_code == 409
    client.post("/api/v1/markets/brokerage/open", json=OPEN)
    assert buy(client, 10).status_code == 409
    assert fake.journals == [] and fake.orders == []


def test_a_buy_moves_cash_to_alpaca_then_places_the_order(env):
    client, Session, fake = env
    opened(client, fake)
    with Session() as db:
        before = wealth(db, "ada")["net_worth"]
    response = buy(client, 40)
    assert response.status_code == 201, response.text
    assert fake.journals == [(FIRM, "acct-ada", Decimal("40.00"))]
    assert fake.orders == [{"symbol": "SPY", "side": "buy", "notional": Decimal("40.00")}]
    assert cash(Session) == Decimal("60")
    with Session() as db:
        # The money moved, it didn't vanish
        assert wealth(db, "ada")["net_worth"] == before
    buy(client, 5, symbol="BTC", kind="crypto")
    assert fake.orders[-1]["symbol"] == "BTC/USD"


def test_a_rejected_order_brings_the_cash_straight_back(env):
    client, Session, fake = env
    opened(client, fake)
    fake.fail_order = True
    response = buy(client, 40)
    assert response.status_code == 502 and "not tradable" in response.json()["detail"]
    assert fake.journals == [(FIRM, "acct-ada", Decimal("40.00")), ("acct-ada", FIRM, Decimal("40.00"))]
    assert cash(Session) == Decimal("100")
    with Session() as db:
        assert db.query(Transaction).count() == 0


def test_if_the_cash_cant_come_back_at_once_it_is_still_accounted_for(env):
    client, Session, fake = env
    opened(client, fake)
    fake.fail_order, fake.fail_return = True, True
    assert buy(client, 40).status_code == 502
    assert cash(Session) == Decimal("60")
    with Session() as db:
        assert wealth(db, "ada")["markets"] == Decimal("40")
    # Later, the sweep returns it
    fake.fail_return, fake.withdrawable = False, Decimal("40")
    client.get("/api/v1/markets/positions")
    assert cash(Session) == Decimal("100")


def test_not_enough_cash_never_reaches_alpaca(env):
    client, Session, fake = env
    opened(client, fake)
    assert buy(client, 500).status_code == 402
    assert fake.journals == [] and cash(Session) == Decimal("100")


def test_selling_places_an_order_and_proceeds_come_back_once(env):
    client, Session, fake = env
    opened(client, fake)
    buy(client, 50)
    fake.cash = Decimal("0")
    fake.held = [{"symbol": "SPY", "asset_class": "us_equity", "qty": "0.1", "cost_basis": "50", "current_price": "512.5",
                  "market_value": "51.25", "unrealized_pl": "1.25"},
                 {"symbol": "BTCUSD", "asset_class": "crypto", "qty": "0.0001", "cost_basis": "9", "current_price": "95000",
                  "market_value": "9.5", "unrealized_pl": "0.5"}]
    positions = client.get("/api/v1/markets/positions").json()
    assert {(p["asset_type"], p["symbol"]) for p in positions["data"]} == {("etf", "SPY"), ("crypto", "BTC")}
    assert positions["trading_enabled"] is True

    sold = client.post("/api/v1/markets/orders", json={"asset_type": "etf", "symbol": "SPY", "side": "sell", "amount": 20})
    assert sold.status_code == 201 and fake.orders[-1] == {"symbol": "SPY", "side": "sell", "notional": Decimal("20.00")}
    client.post("/api/v1/markets/orders", json={"asset_type": "crypto", "symbol": "BTC", "side": "sell", "sell_all": True})
    assert fake.closed == ["BTCUSD"]

    fake.cash = fake.withdrawable = Decimal("20")
    client.get("/api/v1/markets/positions")
    client.get("/api/v1/markets/positions")
    assert cash(Session) == Decimal("70")
    with Session() as db:
        assert db.query(MarketPosition).filter(MarketPosition.user_id == "ada").count() == 2
        assert db.query(Transaction).filter(Transaction.description == "From your investing account").count() == 1


def test_etf_prices_come_from_alpaca_when_it_is_set_up(env):
    client, _, _ = env
    quotes = client.get("/api/v1/markets/etfs").json()["data"]
    spy = next(q for q in quotes if q["symbol"] == "SPY")
    assert spy["price"] == 512.5 and round(spy["change_percent"], 2) == 2.5
    chart = client.get("/api/v1/markets/etfs/SPY/chart?range=1M").json()["data"]
    assert [point[1] for point in chart] == [500.0, 512.5]


def test_without_alpaca_production_never_trades_on_internal_books(env, monkeypatch):
    client, _, _ = env
    monkeypatch.setattr(alpaca.get_settings(), "alpaca_broker_key", "")
    monkeypatch.setenv("ENABLE_MARKET_TRADING", "true")
    assert markets.trading_enabled() is True
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert markets.trading_enabled() is False
    assert buy(client, 10).status_code == 503
