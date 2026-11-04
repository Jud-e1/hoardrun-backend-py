"""
Confirmed card deposits land in the user's Hoardrun cash exactly once.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_deposit_ledger.py --noconftest --import-mode=importlib
"""

import os
from decimal import Decimal

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.config import Base
from app.database.models import Account, Transaction, TransactionTypeEnum, User
from app.services.deposit_ledger import credit_paystack_charge


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    for user_id in ("ada", "bo"):
        session.add(User(id=user_id, email=f"{user_id}@example.com", password_hash="x", first_name=user_id, last_name="Test"))
    session.commit()
    yield session
    session.close()


def charge(**overrides):
    body = {
        "status": "success",
        "reference": "hoardrun_ada_1234abcd",
        "amount": 250000,
        "currency": "USD",
        "paid_at": "2026-11-02T10:00:00Z",
        "metadata": {"user_id": "ada"},
    }
    body.update(overrides)
    return body


def cash(db, user_id):
    return db.query(Account).filter_by(user_id=user_id, currency="USD").one()


def test_first_deposit_opens_a_cash_account_and_credits_it(db):
    transaction, new = credit_paystack_charge(db, charge(), expected_user_id="ada")
    assert new is True
    assert transaction.transaction_type == TransactionTypeEnum.DEPOSIT
    account = cash(db, "ada")
    assert account.available_balance == Decimal("2500.00")
    assert account.current_balance == Decimal("2500.00")
    assert account.is_primary is True


def test_the_same_payment_is_never_credited_twice(db):
    credit_paystack_charge(db, charge(), expected_user_id="ada")
    # The browser comes back again, then the webhook arrives with metadata as a JSON string
    _, again = credit_paystack_charge(db, charge(), expected_user_id="ada")
    _, webhook = credit_paystack_charge(db, charge(metadata='{"user_id": "ada"}'))
    assert again is False and webhook is False
    assert cash(db, "ada").available_balance == Decimal("2500.00")
    assert db.query(Transaction).count() == 1

    credit_paystack_charge(db, charge(reference="hoardrun_ada_second", amount=1000))
    assert cash(db, "ada").available_balance == Decimal("2510.00")


def test_unpaid_foreign_or_anonymous_charges_add_nothing(db):
    assert credit_paystack_charge(db, charge(status="failed")) is None
    assert credit_paystack_charge(db, charge(status="abandoned")) is None
    assert credit_paystack_charge(db, charge(metadata={})) is None
    with pytest.raises(PermissionError):
        credit_paystack_charge(db, charge(), expected_user_id="bo")
    assert db.query(Transaction).count() == 0
    assert db.query(Account).count() == 0


def test_verify_endpoint_credits_the_signed_in_user_once(db, monkeypatch):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1 import paystack as paystack_api
    from app.auth.dependencies import get_current_user
    from app.database.config import get_db
    from app.models.paystack import PaymentVerificationResponse, TransactionData

    payment = TransactionData(
        id=1, domain="test", status="success", reference="hoardrun_ada_1234abcd", amount=250000,
        gateway_response="Approved", created_at="2026-11-02T10:00:00Z", paid_at="2026-11-02T10:00:00Z",
        channel="card", currency="USD", metadata={"user_id": "ada"},
    )

    class FakePaystack:
        async def verify_payment(self, reference):
            return PaymentVerificationResponse(success=True, message="Verified", transaction=payment)

    monkeypatch.setattr(paystack_api, "get_paystack_service", lambda: FakePaystack())
    from app.config import settings as settings_module
    monkeypatch.setattr(settings_module.get_settings(), "paystack_secret_key", "sk_test_fake", raising=False)
    app = FastAPI()
    app.include_router(paystack_api.router, prefix="/api/v1")
    current = {"user": "ada"}
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=current["user"])
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    assert client.get("/api/v1/paystack/verify/hoardrun_ada_1234abcd").status_code == 200
    assert client.get("/api/v1/paystack/verify/hoardrun_ada_1234abcd").status_code == 200
    assert cash(db, "ada").available_balance == Decimal("2500.00")

    current["user"] = "bo"
    assert client.get("/api/v1/paystack/verify/hoardrun_ada_1234abcd").status_code == 403
    assert db.query(Account).filter_by(user_id="bo").count() == 0
