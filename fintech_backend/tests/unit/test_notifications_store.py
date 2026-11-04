"""
Notifications: stored per user and raised by real money events.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_notifications_store.py --noconftest --import-mode=importlib
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

from app.api.v1 import budgets_store, cash, notifications_store, savings_store
from app.api.v1.savings_store import AutoSavePlan, FixedDeposit
from app.auth.dependencies import get_current_user_id
from app.database.config import Base, get_db
from app.database.models import Account, AccountTypeEnum, User
from app.services.deposit_ledger import credit_deposit
from app.services.inbox import notify


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
    for module in (notifications_store, cash, savings_store, budgets_store):
        app.include_router(module.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    who = {"id": "ada"}
    app.dependency_overrides[get_current_user_id] = lambda: who["id"]
    return TestClient(app), Session, who


def inbox(client):
    return client.get("/api/v1/notifications").json()


def test_inbox_read_seen_delete(env):
    client, Session, _ = env
    with Session() as db:
        notify(db, "ada", "info", "One", "First")
        notify(db, "ada", "info", "Two", "Second")
        db.commit()
    box = inbox(client)
    assert box["unread"] == 2 and sorted(n["title"] for n in box["items"]) == ["One", "Two"]
    first = box["items"][0]["id"]

    assert client.post(f"/api/v1/notifications/{first}/read").json()["read"] is True
    assert inbox(client)["unread"] == 1
    client.post("/api/v1/notifications/seen")
    assert all(n["seen"] for n in inbox(client)["items"])
    client.post("/api/v1/notifications/read-all")
    assert inbox(client)["unread"] == 0

    assert client.delete(f"/api/v1/notifications/{first}").json() == {"deleted": True}
    assert len(inbox(client)["items"]) == 1
    client.delete("/api/v1/notifications")
    assert inbox(client)["items"] == []


def test_people_only_see_their_own(env):
    client, Session, who = env
    with Session() as db:
        note = notify(db, "ada", "security", "Private", "Only Ada")
        db.commit()
        note_id = note.id
    who["id"] = "kofi"
    assert inbox(client)["items"] == []
    assert client.post(f"/api/v1/notifications/{note_id}/read").status_code == 404
    assert client.delete(f"/api/v1/notifications/{note_id}").status_code == 404


def test_same_key_notifies_once(env):
    client, Session, _ = env
    with Session() as db:
        assert notify(db, "ada", "info", "A", "a", key="k1") is not None
        assert notify(db, "ada", "info", "A again", "a", key="k1") is None
        db.commit()
        assert notify(db, "ada", "info", "A later", "a", key="k1") is None
    assert len(inbox(client)["items"]) == 1


def test_deposit_notifies_once(env):
    client, Session, _ = env
    with Session() as db:
        credit_deposit(db, user_id="ada", reference="PSK-REF-0001", amount_minor=2500, currency="USD")
        # Paystack can confirm the same payment twice (verify + webhook)
        credit_deposit(db, user_id="ada", reference="PSK-REF-0001", amount_minor=2500, currency="USD")
    items = inbox(client)["items"]
    assert [n["title"] for n in items] == ["Money added"]
    assert "$25.00" in items[0]["message"]


def test_send_notifies_both_people(env):
    client, _, who = env
    sent = client.post("/api/v1/cash/send", json={"recipient_email": "kofi@example.com", "amount": 40, "note": "Lunch"})
    assert sent.status_code == 201
    assert inbox(client)["items"][0]["title"] == "Sent $40.00 to Kofi B."
    who["id"] = "kofi"
    received = inbox(client)["items"][0]
    assert received["title"] == "You received $40.00" and "Lunch" in received["message"]


def test_goal_reached_notifies(env):
    client, _, _ = env
    goal = client.post("/api/v1/savings/goals", json={"name": "Bike", "targetAmount": 100, "monthlyContribution": 10, "category": "Fun", "isAutoSave": False}).json()
    client.post(f"/api/v1/savings/goals/{goal['id']}/contribute", json={"amount": 100})
    assert inbox(client)["items"][0]["title"] == "Goal reached: Bike"


def test_deposit_maturity_and_skipped_auto_save_notify(env):
    client, Session, _ = env
    fd = client.post("/api/v1/savings/fixed-deposits", json={"amount": 100, "termMonths": 12}).json()
    plan = client.post("/api/v1/savings/automated-savings", json={"name": "Big", "amount": 1000, "frequency": "MONTHLY"}).json()
    with Session() as db:
        db.get(FixedDeposit, fd["id"]).maturity_date = date.today()
        db.commit()
    client.get("/api/v1/savings/fixed-deposits")
    titles = [n["title"] for n in inbox(client)["items"]]
    assert "Fixed deposit paid out" in titles
    assert "Auto-save skipped: Big" in titles
    # Reading savings again doesn't repeat the same skip
    client.get("/api/v1/savings/automated-savings")
    assert [n["title"] for n in inbox(client)["items"]].count("Auto-save skipped: Big") == 1


def test_budget_alerts_once_per_month(env):
    client, _, _ = env
    client.post("/api/v1/budgets", json={"name": "Sending", "category": "transfers", "budgeted_amount": 50})
    # Sends are recorded as transfers, so this one puts the budget past its limit
    client.post("/api/v1/cash/send", json={"recipient_email": "kofi@example.com", "amount": 60})
    client.get("/api/v1/budgets")
    titles = [n["title"] for n in inbox(client)["items"]]
    assert titles.count("Over your Sending budget") == 1
