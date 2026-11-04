"""
Savings goals, fixed deposits and auto-save, stored in the database.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_savings_store.py --noconftest --import-mode=importlib
"""

import os
from datetime import date, timedelta
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
from app.api.v1.savings_store import AutoSavePlan, FixedDeposit
from app.auth.dependencies import get_current_user_id
from app.database.config import Base, get_db
from app.database.models import Account, AccountTypeEnum, Transaction, User

GOAL = {"name": "Laptop", "targetAmount": 1000, "monthlyContribution": 100, "category": "Tech", "isAutoSave": False}


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(User(id="ada", email="ada@example.com", password_hash="x", first_name="Ada", last_name="Mensah"))
        db.add(User(id="kofi", email="kofi@example.com", password_hash="x", first_name="Kofi", last_name="Boateng"))
        db.add(Account(id="acct-ada", user_id="ada", account_number="ACCTADA0000001", account_name="Cash (USD)",
                       account_type=AccountTypeEnum.CHECKING, currency="USD", is_primary=True,
                       current_balance=Decimal("500"), available_balance=Decimal("500")))
        db.commit()

    app = FastAPI()
    app.include_router(savings_store.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    who = {"id": "ada"}
    app.dependency_overrides[get_current_user_id] = lambda: who["id"]
    return TestClient(app), Session, who


def cash(Session) -> Decimal:
    with Session() as db:
        return Decimal(db.get(Account, "acct-ada").available_balance)


def test_goal_lifecycle_moves_real_cash(env):
    client, Session, _ = env
    goal = client.post("/api/v1/savings/goals", json=GOAL).json()
    assert goal["currentAmount"] == 0 and goal["progress"] == 0

    added = client.post(f"/api/v1/savings/goals/{goal['id']}/contribute", json={"amount": 250}).json()
    assert added["currentAmount"] == 250 and added["progress"] == 25 and added["cashAvailable"] == 250
    assert cash(Session) == Decimal("250")

    client.post(f"/api/v1/savings/goals/{goal['id']}/withdraw", json={"amount": 50})
    assert cash(Session) == Decimal("300")

    edited = client.patch(f"/api/v1/savings/goals/{goal['id']}", json={"name": "New laptop", "targetAmount": 200}).json()
    assert edited["name"] == "New laptop" and edited["progress"] == 100

    deleted = client.delete(f"/api/v1/savings/goals/{goal['id']}").json()
    assert deleted["returnedToCash"] == 200
    assert cash(Session) == Decimal("500")
    assert client.get("/api/v1/savings/goals").json() == []
    with Session() as db:
        # Every move is on the ledger: in, out, and the close
        assert db.query(Transaction).filter(Transaction.user_id == "ada").count() == 3


def test_goal_completes_when_target_reached(env):
    client, _, _ = env
    goal = client.post("/api/v1/savings/goals", json={**GOAL, "targetAmount": 100}).json()
    done = client.post(f"/api/v1/savings/goals/{goal['id']}/contribute", json={"amount": 100}).json()
    assert done["isCompleted"] is True


def test_cannot_save_more_than_cash(env):
    client, Session, _ = env
    goal = client.post("/api/v1/savings/goals", json=GOAL).json()
    response = client.post(f"/api/v1/savings/goals/{goal['id']}/contribute", json={"amount": 900})
    assert response.status_code == 402
    assert cash(Session) == Decimal("500")


def test_cannot_withdraw_more_than_goal_holds(env):
    client, _, _ = env
    goal = client.post("/api/v1/savings/goals", json=GOAL).json()
    client.post(f"/api/v1/savings/goals/{goal['id']}/contribute", json={"amount": 10})
    assert client.post(f"/api/v1/savings/goals/{goal['id']}/withdraw", json={"amount": 20}).status_code == 400


def test_someone_else_cannot_touch_my_goal(env):
    client, _, who = env
    goal = client.post("/api/v1/savings/goals", json=GOAL).json()
    who["id"] = "kofi"
    assert client.get("/api/v1/savings/goals").json() == []
    assert client.patch(f"/api/v1/savings/goals/{goal['id']}", json={"name": "Mine"}).status_code == 404
    assert client.delete(f"/api/v1/savings/goals/{goal['id']}").status_code == 404


def test_past_deadline_is_refused(env):
    client, _, _ = env
    past = (date.today() - timedelta(days=1)).isoformat()
    assert client.post("/api/v1/savings/goals", json={**GOAL, "deadline": past}).status_code == 400


def test_fixed_deposit_locks_cash_and_pays_interest_at_maturity(env):
    client, Session, _ = env
    deposit = client.post("/api/v1/savings/fixed-deposits", json={"amount": 200, "termMonths": 12}).json()
    assert deposit["rate"] == 4.5 and deposit["interest"] == 9.0 and deposit["maturityAmount"] == 209.0
    assert cash(Session) == Decimal("300")

    with Session() as db:
        db.get(FixedDeposit, deposit["id"]).maturity_date = date.today()
        db.commit()
    deposits = client.get("/api/v1/savings/fixed-deposits").json()
    assert deposits[0]["status"] == "matured"
    assert cash(Session) == Decimal("509")


def test_breaking_a_deposit_returns_principal_only(env):
    client, Session, _ = env
    deposit = client.post("/api/v1/savings/fixed-deposits", json={"amount": 100, "termMonths": 6}).json()
    broken = client.post(f"/api/v1/savings/fixed-deposits/{deposit['id']}/break").json()
    assert broken["status"] == "broken"
    assert cash(Session) == Decimal("500")
    assert client.post(f"/api/v1/savings/fixed-deposits/{deposit['id']}/break").status_code == 400


def test_auto_save_runs_when_due_and_skips_without_cash(env):
    client, Session, _ = env
    plan = client.post("/api/v1/savings/automated-savings", json={"name": "Daily", "amount": 200, "frequency": "DAILY"}).json()
    # Starts today, so the first run happens straight away
    assert plan["savedTotal"] == 200 and plan["runs"] == 1
    assert cash(Session) == Decimal("300")

    with Session() as db:
        db.get(AutoSavePlan, plan["id"]).next_run = date.today() - timedelta(days=2)
        db.commit()
    plans = client.get("/api/v1/savings/automated-savings").json()
    # Three runs fall due; cash covers one more, then the rest are skipped
    assert plans[0]["savedTotal"] == 400 and plans[0]["runs"] == 2
    assert "not enough cash" in plans[0]["lastStatus"]
    assert cash(Session) == Decimal("100")

    closed = client.delete(f"/api/v1/savings/automated-savings/{plan['id']}").json()
    assert closed["returnedToCash"] == 400
    assert cash(Session) == Decimal("500")


def test_paused_plan_does_not_run(env):
    client, Session, _ = env
    plan = client.post("/api/v1/savings/automated-savings",
                       json={"name": "Weekly", "amount": 10, "frequency": "WEEKLY", "startDate": (date.today() + timedelta(days=3)).isoformat()}).json()
    client.patch(f"/api/v1/savings/automated-savings/{plan['id']}", json={"isActive": False})
    with Session() as db:
        db.get(AutoSavePlan, plan["id"]).next_run = date.today() - timedelta(days=1)
        db.commit()
    assert client.get("/api/v1/savings/automated-savings").json()[0]["runs"] == 0
    assert cash(Session) == Decimal("500")


def test_stats_add_up(env):
    client, _, _ = env
    goal = client.post("/api/v1/savings/goals", json=GOAL).json()
    client.post(f"/api/v1/savings/goals/{goal['id']}/contribute", json={"amount": 100})
    client.post("/api/v1/savings/fixed-deposits", json={"amount": 100, "termMonths": 12})
    stats = client.get("/api/v1/savings/stats").json()
    assert stats["total_savings"] == 200
    assert stats["monthly_growth"] == 200
    assert stats["next_milestone"] == 900
    assert client.get("/api/v1/savings/insights").json()["recommendations"]
