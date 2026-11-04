"""
Net worth across cash, savings and investments.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_wealth.py --noconftest --import-mode=importlib
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

from app.api.v1 import savings_store
from app.auth.dependencies import get_current_user_id
from app.database.config import Base, get_db
from app.database.market_models import MarketPosition
from app.database.models import Account, AccountTypeEnum, User
from app.services.wealth import wealth


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        for uid, cash in (("ada", "1000"), ("kofi", "777")):
            db.add(User(id=uid, email=f"{uid}@example.com", password_hash="x", first_name=uid.title(), last_name="Test"))
            db.add(Account(id=f"acct-{uid}", user_id=uid, account_number=f"ACCT{uid.upper()}000001", account_name="Cash",
                           account_type=AccountTypeEnum.CHECKING, currency="USD",
                           current_balance=Decimal(cash), available_balance=Decimal(cash)))
        db.add(MarketPosition(id="p1", user_id="ada", asset_type="crypto", symbol="BTC", quantity=Decimal("0.01"), cost_basis=Decimal("150")))
        db.commit()

    app = FastAPI()
    app.include_router(savings_store.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user_id] = lambda: "ada"
    return TestClient(app), Session


def owned(Session):
    with Session() as db:
        return wealth(db, "ada")


def test_moving_money_keeps_net_worth(env):
    client, Session = env
    before = owned(Session)
    assert before["cash"] == 1000 and before["investments"] == 150 and before["net_worth"] == 1150

    goal = client.post("/api/v1/savings/goals", json={"name": "Car", "targetAmount": 5000, "monthlyContribution": 100, "category": "Car", "isAutoSave": False}).json()
    client.post(f"/api/v1/savings/goals/{goal['id']}/contribute", json={"amount": 300})
    client.post("/api/v1/savings/fixed-deposits", json={"amount": 200, "termMonths": 6})
    client.post("/api/v1/savings/automated-savings", json={"name": "Daily", "amount": 50, "frequency": "DAILY"})

    after = owned(Session)
    assert after["cash"] == 450
    assert after["savings_goals"] == 300 and after["fixed_deposits"] == 200 and after["auto_save"] == 50
    assert after["savings"] == 550
    assert after["net_worth"] == before["net_worth"]


def test_closed_savings_stop_counting_but_money_returns(env):
    client, Session = env
    deposit = client.post("/api/v1/savings/fixed-deposits", json={"amount": 200, "termMonths": 6}).json()
    client.post(f"/api/v1/savings/fixed-deposits/{deposit['id']}/break")
    after = owned(Session)
    assert after["fixed_deposits"] == 0 and after["cash"] == 1000 and after["net_worth"] == 1150


def test_only_your_own_money(env):
    _, Session = env
    with Session() as db:
        kofi = wealth(db, "kofi")
    assert kofi["cash"] == 777 and kofi["investments"] == 0 and kofi["net_worth"] == 777
