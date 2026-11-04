"""
Daily reconciliation, run after money has moved through every feature.

If any feature changes a balance without the matching ledger entry, or loses track of money,
the report says so. Outside services (Plaid, Stripe, Alpaca) are faked.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_reconciliation.py --noconftest --import-mode=importlib
"""

import os
from decimal import Decimal
from types import SimpleNamespace

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import bank_links, brokerage, cash, issued_cards, markets, savings_store
from app.auth.dependencies import get_current_user_id
from app.database import registry  # noqa: F401 - every table
from app.database.config import Base, get_db
from app.database.models import Account, User
from app.services import alpaca, email_service, reconciliation
from app.services.deposit_ledger import credit_deposit

FIRM = "firm-1"


class FakePlaid:
    def __init__(self):
        self.feed, self.count = [], 0

    def exchange(self, public_token):
        return {"access_token": "access-sandbox-x", "item_id": "item-1"}

    def item(self, token):
        return {"item_id": "item-1", "institution_id": "ins_1", "institution_name": "First Platypus Bank", "error_code": None}

    def accounts(self, token):
        return [{"account_id": "acc-1", "name": "Checking", "official_name": None, "mask": "0000", "type": "depository",
                 "subtype": "checking", "available": 5000.0, "current": 5000.0, "limit": None, "currency": "USD"}]

    def authorize(self, **_):
        return {"id": "auth", "decision": "approved", "reason": None}

    def create_transfer(self, **_):
        self.count += 1
        return {"id": f"tr-{self.count}", "status": "pending"}

    def events(self, after_id, count=25):
        return [e for e in self.feed if e["event_id"] > after_id][:count]

    def push(self, transfer_id, event_type):
        self.feed.append({"event_id": len(self.feed) + 1, "transfer_id": transfer_id, "event_type": event_type, "failure_reason": None})


class FakeAlpaca:
    firm = FIRM

    def __init__(self):
        self.cash = Decimal("0")
        self.withdrawable = Decimal("0")

    def create_account(self, payload):
        return {"id": "acct-ada", "status": "ACTIVE"}

    def account(self, account_id):
        return {"status": "ACTIVE"}

    def journal(self, from_account, to_account, amount, description):
        self.cash += amount if from_account == FIRM else -amount
        if from_account != FIRM:
            self.withdrawable -= amount
        return {"status": "executed"}

    def order(self, account_id, **_):
        return {"id": "ord-1", "status": "accepted"}

    def get_order(self, account_id, order_id):
        return {"status": "filled", "filled_qty": "0.05", "filled_avg_price": "600"}

    def trading_account(self, account_id):
        return {"cash": str(self.cash), "cash_withdrawable": str(self.withdrawable)}

    def positions(self, account_id):
        return [{"symbol": "SPY", "asset_class": "us_equity", "qty": "0.05", "cost_basis": "30", "current_price": "600",
                 "market_value": "30", "unrealized_pl": "0"}]


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        for uid, name in (("ada", "Ada"), ("kofi", "Kofi")):
            db.add(User(id=uid, email=f"{uid}@example.com", password_hash="x", first_name=name, last_name="Test", status="active"))
        db.commit()

    settings = alpaca.get_settings()
    for key, value in {"persona_api_key": "", "alpaca_broker_key": "k", "alpaca_broker_secret": "s",
                       "alpaca_firm_account_id": FIRM, "stripe_secret_key": "sk_test_x"}.items():
        monkeypatch.setattr(settings, key, value)
    plaid, broker = FakePlaid(), FakeAlpaca()
    monkeypatch.setattr(bank_links, "get_gateway", lambda: plaid)
    monkeypatch.setattr(alpaca, "get_broker", lambda: broker)
    cards = SimpleNamespace(create=lambda params=None, options=None: SimpleNamespace(id="ich_1") if "type" in (params or {}) and params.get("type") == "individual"
                            else {"id": "ic_1", "last4": "4242", "brand": "Visa", "exp_month": 1, "exp_year": 2030},
                            update=lambda *a, **k: None)
    monkeypatch.setattr(issued_cards, "get_client", lambda: SimpleNamespace(v1=SimpleNamespace(issuing=SimpleNamespace(cardholders=cards, cards=cards))))
    monkeypatch.setattr(email_service, "deliver", lambda *a: True)
    monkeypatch.setattr(email_service, "_pool", SimpleNamespace(submit=lambda fn, *a: fn(*a)))

    app = FastAPI()
    for module in (savings_store, cash, bank_links, issued_cards, brokerage, markets):
        app.include_router(module.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user_id] = lambda: "ada"
    return TestClient(app), Session, plaid, broker


def ok(response):
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_money_through_every_feature_reconciles_to_the_cent(env):
    client, Session, plaid, broker = env
    with Session() as db:
        credit_deposit(db, user_id="ada", reference="card-1", amount_minor=100000, currency="USD")  # +1000

    # Savings: into a goal and partly back, a fixed deposit opened and broken
    goal = ok(client.post("/api/v1/savings/goals", json={"name": "Trip", "targetAmount": 500, "monthlyContribution": 50}))
    goal_id = goal.get("id") or goal["data"]["id"]
    ok(client.post(f"/api/v1/savings/goals/{goal_id}/contribute", json={"amount": 100}))
    ok(client.post(f"/api/v1/savings/goals/{goal_id}/withdraw", json={"amount": 30}))
    deposit = ok(client.post("/api/v1/savings/fixed-deposits", json={"amount": 200, "termMonths": 6}))
    ok(client.post(f"/api/v1/savings/fixed-deposits/{deposit.get('id') or deposit['data']['id']}/break"))

    # A send to another member stays inside Hoardrun
    ok(client.post("/api/v1/cash/send", json={"recipient_email": "kofi@example.com", "amount": 50}))

    # Bank: a withdrawal that comes back, and a deposit that arrives
    ok(client.post("/api/v1/plaid/exchange-token", json={"public_token": "public-sandbox-1"}))
    ok(client.post("/api/v1/plaid/transfers/withdraw", json={"account_id": "acc-1", "amount": 100}))
    plaid.push("tr-1", "returned")
    ok(client.post("/api/v1/plaid/transfers/deposit", json={"account_id": "acc-1", "amount": 70}))
    plaid.push("tr-2", "settled")
    ok(client.post("/api/v1/plaid/transfers/sync"))

    # Card: held, charged a little less, closed, then partly refunded
    ok(client.post("/api/v1/issuing/cards", json={"accept_terms": True, "billing": {
        "line1": "1 Market St", "city": "San Francisco", "state": "CA", "postal_code": "94105"}}))
    with Session() as db:
        assert issued_cards.decide(db, {"id": "iauth_1", "card": {"id": "ic_1"}, "pending_request": {"amount": 2500, "currency": "usd"},
                                        "merchant_data": {"name": "Cafe", "category": "eating_places_restaurants"}})[0]
        issued_cards.apply_transaction(db, {"id": "ipi_1", "type": "capture", "amount": -2000, "card": "ic_1", "authorization": "iauth_1"})
        issued_cards.authorization_closed(db, {"id": "iauth_1", "status": "closed"})
        issued_cards.apply_transaction(db, {"id": "ipi_2", "type": "refund", "amount": 500, "card": "ic_1", "authorization": None})

    # Investing: $40 to Alpaca, $10 of it swept back
    ok(client.post("/api/v1/markets/brokerage/open", json={
        "date_of_birth": "1990-01-01", "ssn": "123-45-6789", "phone": "+14155550100", "employment_status": "employed",
        "address": {"line1": "1 Market St", "city": "San Francisco", "state": "CA", "postal_code": "94105"}, "accept_agreements": True}))
    ok(client.post("/api/v1/markets/orders", json={"asset_type": "etf", "symbol": "SPY", "side": "buy", "amount": 40}))
    broker.cash, broker.withdrawable = Decimal("10"), Decimal("10")
    ok(client.get("/api/v1/markets/positions?asset_type=etf"))

    with Session() as db:
        report = reconciliation.build(db)
    assert report.problems == [], report.problems
    owners = {o.user_id: o for o in report.owners}
    # 1000 in; 70 savings left in the goal; 50 sent to Kofi; +70 from the bank; 15 net on the card; 40 to Alpaca, 10 back
    assert owners["ada"].savings == Decimal("70")
    assert owners["ada"].cash == Decimal("1000") - 70 - 50 + 70 - 15 - 40 + 10
    assert owners["kofi"].cash == Decimal("50")
    assert owners["ada"].at_broker == Decimal("30")
    assert report.total("held_by_hoardrun") == Decimal("1000") + 70 - 15 - 40 + 10
    lines = reconciliation.summary(report, fbo_balance=report.total("held_by_hoardrun"))
    assert any("difference +0.00" in line for line in lines)


def test_a_balance_changed_without_a_ledger_entry_is_caught(env):
    _, Session, _, _ = env
    with Session() as db:
        credit_deposit(db, user_id="ada", reference="card-2", amount_minor=5000, currency="USD")
        account = db.query(Account).filter(Account.user_id == "ada").one()
        account.current_balance = Decimal(account.current_balance) + 7
        account.available_balance = Decimal(account.available_balance) + 7
        db.commit()
        report = reconciliation.build(db)
    assert any("transactions add up to 50.00" in problem for problem in report.problems)
    lines = reconciliation.summary(report, fbo_balance=Decimal("50"))
    assert any("difference -7.00" in line for line in lines)
