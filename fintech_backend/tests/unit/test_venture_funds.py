"""
Venture funds and buying shares in them with Hoardrun cash.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_venture_funds.py --noconftest --import-mode=importlib
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

from app.api.v1 import venture
from app.auth.dependencies import get_current_user_id
from app.database import venture_models  # noqa: F401 - registers the tables
from app.database.config import Base, get_db
from app.database.models import Account, AccountTypeEnum, Transaction, TransactionTypeEnum, User


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        for user_id in ("manager", "investor"):
            db.add(User(id=user_id, email=f"{user_id}@example.com", password_hash="x", first_name=user_id, last_name="Test"))
        db.commit()

    app = FastAPI()
    app.include_router(venture.router, prefix="/api/v1")
    current = {"user": "manager"}

    def session():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user_id] = lambda: current["user"]
    return TestClient(app), current, Session


def fund(**overrides):
    body = {
        "firm_name": "Harbor Ventures",
        "fund_name": "Harbor Seed Fund I",
        "thesis": "Seed rounds in African fintech and logistics",
        "sectors": ["Fintech", "Logistics"],
        "stage": "seed",
        "share_price": "100",
        "total_shares": 1000,
        "min_shares": 2,
        "term_years": 8,
        "management_fee": "2",
        "carry": "20",
    }
    body.update(overrides)
    return body


def give_cash(Session, user_id, amount):
    with Session() as db:
        db.add(Account(id=f"acct-{user_id}", user_id=user_id, account_number=f"ACCT{user_id.upper():0>10}"[:20], account_name="Cash",
                       account_type=AccountTypeEnum.CHECKING, currency="USD", is_primary=True,
                       current_balance=Decimal(amount), available_balance=Decimal(amount)))
        db.commit()


def test_registered_fund_is_listed_with_its_size(env):
    client, current, _ = env
    assert client.get("/api/v1/venture-funds").json()["total"] == 0

    created = client.post("/api/v1/venture-funds", json=fund())
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["target_size"] == 100000
    assert data["shares_left"] == 1000
    assert data["is_manager"] is True

    current["user"] = "investor"
    listed = client.get("/api/v1/venture-funds").json()
    assert listed["total"] == 1
    assert listed["data"][0]["is_manager"] is False
    assert listed["cash_available"] == 0


def test_buying_takes_cash_records_a_transaction_and_counts_shares(env):
    client, current, Session = env
    fund_id = client.post("/api/v1/venture-funds", json=fund()).json()["data"]["id"]

    current["user"] = "investor"
    broke = client.post(f"/api/v1/venture-funds/{fund_id}/buy", json={"shares": 3})
    assert broke.status_code == 402
    assert "Add money first" in broke.json()["detail"]

    give_cash(Session, "investor", "1000")
    bought = client.post(f"/api/v1/venture-funds/{fund_id}/buy", json={"shares": 3})
    assert bought.status_code == 201
    result = bought.json()["data"]
    assert result["amount"] == 300
    assert result["cash_available"] == 700
    assert result["fund"]["shares_sold"] == 3
    assert result["fund"]["my_shares"] == 3

    with Session() as db:
        account = db.get(Account, "acct-investor")
        assert account.available_balance == Decimal("700.00")
        assert account.current_balance == Decimal("700.00")
        transaction = db.query(Transaction).filter_by(user_id="investor").one()
        assert transaction.transaction_type == TransactionTypeEnum.INVESTMENT
        assert transaction.amount == Decimal("300.00")

    holdings = client.get("/api/v1/venture-funds/holdings").json()
    assert holdings["total_value"] == 300


def test_purchase_limits(env):
    client, current, Session = env
    fund_id = client.post("/api/v1/venture-funds", json=fund(total_shares=10, min_shares=2)).json()["data"]["id"]

    assert client.post(f"/api/v1/venture-funds/{fund_id}/buy", json={"shares": 2}).status_code == 400  # manager

    current["user"] = "investor"
    give_cash(Session, "investor", "100000")
    assert client.post(f"/api/v1/venture-funds/{fund_id}/buy", json={"shares": 1}).status_code == 400  # below minimum
    assert client.post(f"/api/v1/venture-funds/{fund_id}/buy", json={"shares": 11}).status_code == 409  # more than left
    assert client.post(f"/api/v1/venture-funds/{fund_id}/buy", json={"shares": 10}).status_code == 201
    sold_out = client.get(f"/api/v1/venture-funds/{fund_id}").json()["data"]
    assert sold_out["is_open"] is False
    assert client.post(f"/api/v1/venture-funds/{fund_id}/buy", json={"shares": 2}).status_code == 409


def test_bad_fund_details_are_rejected(env):
    client, _, _ = env
    assert client.post("/api/v1/venture-funds", json=fund(min_shares=5000)).status_code == 422
    assert client.post("/api/v1/venture-funds", json=fund(sectors=[])).status_code == 422
    assert client.post("/api/v1/venture-funds", json=fund(stage="ipo")).status_code == 422
    assert client.post("/api/v1/venture-funds", json=fund(closes_on="2001-01-01")).status_code == 422


def test_fund_can_only_be_removed_by_its_manager_before_anyone_buys(env):
    client, current, Session = env
    fund_id = client.post("/api/v1/venture-funds", json=fund()).json()["data"]["id"]
    current["user"] = "investor"
    assert client.delete(f"/api/v1/venture-funds/{fund_id}").status_code == 403
    give_cash(Session, "investor", "1000")
    client.post(f"/api/v1/venture-funds/{fund_id}/buy", json={"shares": 2})
    current["user"] = "manager"
    assert client.delete(f"/api/v1/venture-funds/{fund_id}").status_code == 409
