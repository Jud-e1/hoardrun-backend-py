"""
Exporting your data and closing your account.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_account_lifecycle.py --noconftest --import-mode=importlib
"""

import os
import uuid
from datetime import datetime
from decimal import Decimal

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import account_lifecycle
from app.api.v1.budgets_store import Budget
from app.auth import dependencies, passwords
from app.auth.dependencies import get_current_user_id
import bcrypt
from app.database.config import Base, get_db
from app.database.models import (
    Account, AccountStatusEnum, AccountTypeEnum, PaymentMethodEnum, Transaction, TransactionDirectionEnum,
    TransactionStatusEnum, TransactionTypeEnum, User,
)
from app.services.card_vault import SavedCard
from app.services.inbox import notify

PASSWORD = "Correct-Horse-9"


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(User(id="ada", email="ada@example.com", password_hash=bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), first_name="Ada",
                    last_name="Mensah", phone_number="+15551234567", status="active"))
        db.add(Account(id="acct-ada", user_id="ada", account_number="ACCTADA0000001", account_name="Cash",
                       account_type=AccountTypeEnum.CHECKING, currency="USD", current_balance=0, available_balance=0))
        db.add(Transaction(id=str(uuid.uuid4()), user_id="ada", account_id="acct-ada", transaction_type=TransactionTypeEnum.DEPOSIT,
                           status=TransactionStatusEnum.COMPLETED, direction=TransactionDirectionEnum.INBOUND, amount=Decimal("20"),
                           currency="USD", description="Card deposit", payment_method=PaymentMethodEnum.CARD,
                           reference_number="REF-HIST-0001", transaction_date=datetime.utcnow()))
        db.add(SavedCard(id="card-1", user_id="ada", last4="4242", brand="visa"))
        db.add(Budget(id="b1", user_id="ada", name="Food", category="food", monthly_limit=Decimal("100")))
        notify(db, "ada", "info", "Hello", "Welcome")
        db.commit()

    app = FastAPI()
    app.include_router(account_lifecycle.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user_id] = lambda: "ada"
    return TestClient(app), Session


def close(client, password=PASSWORD, confirm="CLOSE"):
    return client.post("/api/v1/account/close", json={"password": password, "confirm": confirm})


def test_export_has_everything(env):
    client, _ = env
    data = client.get("/api/v1/account/export").json()
    assert data["profile"]["email"] == "ada@example.com"
    assert len(data["transactions"]) == 1 and data["cards"][0]["last4"] == "4242"
    assert data["budgets"][0]["name"] == "Food" and data["notifications"][0]["title"] == "Hello"
    # Never full card details or the password
    text = str(data)
    assert "password" not in text and "4242424242424242" not in text


def test_wrong_password_or_missing_confirm_keeps_account(env):
    client, Session = env
    assert close(client, password="nope").status_code == 401
    assert close(client, confirm="close please").status_code == 422
    with Session() as db:
        assert db.get(User, "ada").status == "active"


def test_money_blocks_closing(env):
    client, Session = env
    with Session() as db:
        account = db.get(Account, "acct-ada")
        account.current_balance = account.available_balance = Decimal("12.50")
        db.commit()
    response = close(client)
    assert response.status_code == 409 and "$12.50 in cash" in response.json()["detail"]
    assert client.get("/api/v1/account/close-check").json()["blockers"] == ["$12.50 in cash"]


def test_closing_scrubs_person_and_keeps_records(env):
    client, Session = env
    assert close(client).json() == {"closed": True}
    with Session() as db:
        user = db.get(User, "ada")
        assert user.status == "deactivated" and user.is_active is False
        assert user.email.startswith("closed-") and user.first_name == "Closed" and user.phone_number is None
        assert not passwords.verify_password(PASSWORD, user.password_hash)
        assert db.get(Account, "acct-ada").status == AccountStatusEnum.CLOSED
        # Financial history stays for record-keeping; personal extras go
        assert db.query(Transaction).filter(Transaction.user_id == "ada").count() == 1
        assert db.query(SavedCard).count() == 0 and db.query(Budget).count() == 0


def test_closed_accounts_are_refused_on_every_request(env, monkeypatch):
    client, Session = env
    close(client)
    monkeypatch.setattr("app.database.config.SessionLocal", Session)
    assert dependencies.account_is_closed("ada") is True
    assert dependencies.account_is_closed("someone-else") is False
