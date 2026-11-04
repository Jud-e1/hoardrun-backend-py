"""
Instant sends between Hoardrun users.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_cash_send.py --noconftest --import-mode=importlib
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

from app.api.v1 import cash
from app.auth.dependencies import get_current_user_id
from app.database.config import Base, get_db
from app.database.models import Account, AccountTypeEnum, Transaction, TransactionTypeEnum, User


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(User(id="ada", email="ada@example.com", password_hash="x", first_name="Ada", last_name="Mensah"))
        db.add(User(id="kofi", email="Kofi@Example.com", password_hash="x", first_name="Kofi", last_name="Boateng"))
        db.add(Account(id="acct-ada", user_id="ada", account_number="ACCTADA0000001", account_name="Cash",
                       account_type=AccountTypeEnum.CHECKING, currency="USD", is_primary=True,
                       current_balance=Decimal("500"), available_balance=Decimal("500")))
        db.commit()
    app = FastAPI()
    app.include_router(cash.router, prefix="/api/v1")

    def session():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user_id] = lambda: "ada"
    return TestClient(app), Session


def test_lookup_shows_only_a_short_name(env):
    client, _ = env
    assert client.get("/api/v1/cash/lookup?email=kofi@example.com").json() == {"found": True, "name": "Kofi B."}
    assert client.get("/api/v1/cash/lookup?email=ada@example.com").json() == {"found": False}
    assert client.get("/api/v1/cash/lookup?email=nobody@example.com").json() == {"found": False}


def test_send_moves_cash_and_records_both_sides(env):
    client, Session = env
    sent = client.post("/api/v1/cash/send", json={"recipient_email": "KOFI@example.com", "amount": "120.50", "note": "Dinner"})
    assert sent.status_code == 201
    assert sent.json()["data"]["recipient_name"] == "Kofi B."
    assert sent.json()["data"]["cash_available"] == pytest.approx(379.50)
    with Session() as db:
        assert db.get(Account, "acct-ada").available_balance == Decimal("379.50")
        kofi_cash = db.query(Account).filter_by(user_id="kofi").one()
        assert kofi_cash.available_balance == Decimal("120.50")
        kinds = sorted(t.transaction_type.value for t in db.query(Transaction))
        assert kinds == [TransactionTypeEnum.TRANSFER_IN.value, TransactionTypeEnum.TRANSFER_OUT.value]
    assert client.get("/api/v1/cash/recent").json()["data"][0]["name"] == "Kofi B."


def test_send_limits(env):
    client, Session = env
    assert client.post("/api/v1/cash/send", json={"recipient_email": "kofi@example.com", "amount": "600"}).status_code == 402
    assert client.post("/api/v1/cash/send", json={"recipient_email": "kofi@example.com", "amount": "0.50"}).status_code == 400
    assert client.post("/api/v1/cash/send", json={"recipient_email": "ada@example.com", "amount": "10"}).status_code == 400
    assert client.post("/api/v1/cash/send", json={"recipient_email": "ghost@example.com", "amount": "10"}).status_code == 404
    with Session() as db:
        assert db.get(Account, "acct-ada").available_balance == Decimal("500.00")
        assert db.query(Transaction).count() == 0
