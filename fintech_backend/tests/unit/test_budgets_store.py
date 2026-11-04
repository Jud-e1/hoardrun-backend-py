"""
Monthly budgets, with spending worked out from real transactions.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_budgets_store.py --noconftest --import-mode=importlib
"""

import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import budgets_store
from app.auth.dependencies import get_current_user_id
from app.database.config import Base, get_db
from app.database.models import (
    Account, AccountTypeEnum, MerchantCategoryEnum as M, PaymentMethodEnum, Transaction, TransactionDirectionEnum,
    TransactionStatusEnum, TransactionTypeEnum, User,
)


def spend(db, user, amount, category, *, direction=TransactionDirectionEnum.OUTBOUND, merchant=None,
          when=None, state=TransactionStatusEnum.COMPLETED):
    when = when or datetime.utcnow()
    db.add(Transaction(
        id=str(uuid.uuid4()), user_id=user, account_id=f"acct-{user}", transaction_type=TransactionTypeEnum.PURCHASE
        if hasattr(TransactionTypeEnum, "PURCHASE") else TransactionTypeEnum.TRANSFER_OUT,
        status=state, direction=direction, amount=Decimal(str(amount)), currency="USD",
        description="test", merchant_name=merchant, merchant_category=category, payment_method=PaymentMethodEnum.OTHER,
        reference_number=f"T-{uuid.uuid4().hex[:10].upper()}", transaction_date=when, created_at=when,
    ))


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        for uid in ("ada", "kofi"):
            db.add(User(id=uid, email=f"{uid}@example.com", password_hash="x", first_name=uid.title(), last_name="Test"))
            db.add(Account(id=f"acct-{uid}", user_id=uid, account_number=f"ACCT{uid.upper()}000001", account_name="Cash",
                           account_type=AccountTypeEnum.CHECKING, currency="USD", current_balance=0, available_balance=0))
        # Ada this month: food 40 + 25, shopping 100, a savings move (not spending), a refund (inbound), a failed charge
        spend(db, "ada", 40, M.GROCERIES)
        spend(db, "ada", 25, M.RESTAURANTS)
        spend(db, "ada", 100, M.RETAIL)
        spend(db, "ada", 300, M.OTHER, merchant="Hoardrun Savings")
        spend(db, "ada", 15, M.GROCERIES, direction=TransactionDirectionEnum.INBOUND)
        spend(db, "ada", 999, M.GROCERIES, state=TransactionStatusEnum.FAILED)
        # Ada last month, and Kofi this month
        spend(db, "ada", 80, M.RESTAURANTS, when=datetime.utcnow().replace(day=1) - timedelta(days=3))
        spend(db, "kofi", 500, M.GROCERIES)
        db.commit()

    app = FastAPI()
    app.include_router(budgets_store.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    who = {"id": "ada"}
    app.dependency_overrides[get_current_user_id] = lambda: who["id"]
    return TestClient(app), who


def test_spent_comes_from_real_transactions(env):
    client, _ = env
    food = client.post("/api/v1/budgets", json={"name": "Food", "category": "food", "budgeted_amount": 200}).json()
    # Groceries and restaurants count; inbound, failed and savings moves don't; Kofi's spending doesn't
    assert food["spent_amount"] == 65 and food["percentage_used"] == 32.5 and food["remaining"] == 135


def test_over_budget_shows_over_100(env):
    client, _ = env
    shop = client.post("/api/v1/budgets", json={"name": "Shopping", "category": "shopping", "budgeted_amount": 80}).json()
    assert shop["percentage_used"] == 125 and shop["remaining"] == -20


def test_saved_and_listed_and_summarised(env):
    client, _ = env
    client.post("/api/v1/budgets", json={"name": "Food", "category": "food", "budgeted_amount": 200})
    client.post("/api/v1/budgets", json={"name": "Shopping", "category": "shopping", "budgeted_amount": 150})
    names = [b["name"] for b in client.get("/api/v1/budgets").json()]
    assert names == ["Food", "Shopping"]
    summary = client.get("/api/v1/budgets/summary").json()
    assert summary["total_budgeted"] == 350 and summary["total_spent"] == 165 and summary["total_remaining"] == 185
    assert summary["overall_percentage_used"] == 47.1


def test_one_budget_per_category(env):
    client, _ = env
    client.post("/api/v1/budgets", json={"name": "Food", "category": "food", "budgeted_amount": 200})
    assert client.post("/api/v1/budgets", json={"name": "Eating", "category": "food", "budgeted_amount": 50}).status_code == 409
    assert client.post("/api/v1/budgets", json={"name": "X", "category": "yachts", "budgeted_amount": 50}).status_code == 400


def test_edit_and_delete(env):
    client, _ = env
    food = client.post("/api/v1/budgets", json={"name": "Food", "category": "food", "budgeted_amount": 200}).json()
    edited = client.patch(f"/api/v1/budgets/{food['id']}", json={"name": "Groceries", "budgeted_amount": 65}).json()
    assert edited["name"] == "Groceries" and edited["percentage_used"] == 100
    assert client.delete(f"/api/v1/budgets/{food['id']}").json() == {"deleted": True}
    assert client.get("/api/v1/budgets").json() == []


def test_someone_else_cannot_touch_my_budget(env):
    client, who = env
    food = client.post("/api/v1/budgets", json={"name": "Food", "category": "food", "budgeted_amount": 200}).json()
    who["id"] = "kofi"
    assert client.get("/api/v1/budgets").json() == []
    assert client.patch(f"/api/v1/budgets/{food['id']}", json={"name": "Mine"}).status_code == 404
    assert client.delete(f"/api/v1/budgets/{food['id']}").status_code == 404


def test_trend_covers_past_months(env):
    client, _ = env
    client.post("/api/v1/budgets", json={"name": "Food", "category": "food", "budgeted_amount": 200})
    points = client.get("/api/v1/budgets/trend?months=2").json()
    assert [p["spent"] for p in points] == [80, 65]
    assert all(p["budgeted"] == 200 for p in points)
