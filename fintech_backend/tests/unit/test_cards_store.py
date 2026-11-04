"""
Saved cards: stored in the database, never with full card numbers, and linked to real deposits.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_cards_store.py --noconftest --import-mode=importlib
"""

import os

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import cards_store
from app.auth.dependencies import get_current_user_id
from app.database.config import Base, get_db
from app.database.models import User
from app.services.card_vault import SavedCard
from app.services.deposit_ledger import credit_paystack_charge

CARD = {"type": "debit_card", "card_holder_name": "Ada Mensah", "card_number_masked": "****4242",
        "expiry_month": 12, "expiry_year": 2030, "card_type": "visa"}
AUTH = {"channel": "card", "last4": "4081", "exp_month": "09", "exp_year": "2031", "card_type": "visa ",
        "bank": "Test Bank", "signature": "SIG_abc123", "authorization_code": "AUTH_secret", "account_name": "ADA MENSAH"}


def charge(reference, amount=5000):
    return {"status": "success", "reference": reference, "amount": amount, "currency": "USD",
            "metadata": {"user_id": "ada"}, "authorization": AUTH}


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(User(id="ada", email="ada@example.com", password_hash="x", first_name="Ada", last_name="Mensah"))
        db.add(User(id="kofi", email="kofi@example.com", password_hash="x", first_name="Kofi", last_name="Boateng"))
        db.commit()

    app = FastAPI()
    app.include_router(cards_store.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    who = {"id": "ada"}
    app.dependency_overrides[get_current_user_id] = lambda: who["id"]
    return TestClient(app), Session, who


def test_added_card_is_saved_and_first_is_default(env):
    client, _, _ = env
    card = client.post("/api/v1/payment-methods", json=CARD).json()
    assert card["card_number_masked"] == "****4242" and card["is_default"] is True and card["status"] == "active"
    second = client.post("/api/v1/payment-methods", json={**CARD, "card_number_masked": "****1111"}).json()
    assert second["is_default"] is False
    assert [c["card_number_masked"] for c in client.get("/api/v1/payment-methods").json()] == ["****4242", "****1111"]


def test_full_card_numbers_are_refused(env):
    client, Session, _ = env
    for number in ("4242424242424242", "4242 4242 4242 4242", "****42424242"):
        assert client.post("/api/v1/payment-methods", json={**CARD, "card_number_masked": number}).status_code == 400
    with Session() as db:
        assert db.query(SavedCard).count() == 0


def test_expired_card_is_refused(env):
    client, _, _ = env
    assert client.post("/api/v1/payment-methods", json={**CARD, "expiry_year": 2020}).status_code == 400


def test_lock_contactless_online_and_limits(env):
    client, _, _ = env
    card = client.post("/api/v1/payment-methods", json=CARD).json()
    url = f"/api/v1/payment-methods/{card['id']}"
    locked = client.put(url, json={"status": "locked", "contactless": False, "online_payments": False}).json()
    assert locked["status"] == "locked" and locked["contactless"] is False and locked["online_payments"] is False
    limited = client.put(url, json={"per_transaction_limit": 200, "monthly_limit": 1500}).json()
    assert limited["per_transaction_limit"] == 200 and limited["monthly_limit"] == 1500
    assert client.put(url, json={"per_transaction_limit": 2000}).status_code == 400
    cleared = client.put(url, json={"per_transaction_limit": 0}).json()
    assert cleared["per_transaction_limit"] is None and cleared["monthly_limit"] == 1500


def test_default_moves_when_removed(env):
    client, _, _ = env
    first = client.post("/api/v1/payment-methods", json=CARD).json()
    second = client.post("/api/v1/payment-methods", json={**CARD, "card_number_masked": "****1111"}).json()
    client.post(f"/api/v1/payment-methods/{second['id']}/set-default")
    assert [c["id"] for c in client.get("/api/v1/payment-methods").json() if c["is_default"]] == [second["id"]]
    client.delete(f"/api/v1/payment-methods/{second['id']}")
    assert client.get("/api/v1/payment-methods").json()[0]["is_default"] is True
    assert client.get("/api/v1/payment-methods").json()[0]["id"] == first["id"]


def test_someone_else_cannot_touch_my_card(env):
    client, _, who = env
    card = client.post("/api/v1/payment-methods", json=CARD).json()
    who["id"] = "kofi"
    assert client.get("/api/v1/payment-methods").json() == []
    assert client.put(f"/api/v1/payment-methods/{card['id']}", json={"status": "locked"}).status_code == 404
    assert client.delete(f"/api/v1/payment-methods/{card['id']}").status_code == 404
    assert client.get(f"/api/v1/payment-methods/{card['id']}/transactions").status_code == 404


def test_card_payment_saves_card_and_links_its_deposits(env):
    client, Session, _ = env
    with Session() as db:
        credit_paystack_charge(db, charge("PSK-ONE-0001", 5000))
        credit_paystack_charge(db, charge("PSK-TWO-0002", 2500))
        # The same payment confirmed twice doesn't add a second deposit or card
        credit_paystack_charge(db, charge("PSK-TWO-0002", 2500))
    cards = client.get("/api/v1/payment-methods").json()
    assert len(cards) == 1
    card = cards[0]
    assert card["card_number_masked"] == "****4081" and card["source"] == "paystack" and card["is_default"] is True
    with Session() as db:
        stored = db.get(SavedCard, card["id"])
        # The chargeable authorization code is never kept
        assert "AUTH_secret" not in str(vars(stored))

    history = client.get(f"/api/v1/payment-methods/{card['id']}/transactions").json()
    assert history["total"] == 75 and len(history["items"]) == 2
    assert history["items"][0]["description"].endswith("•••• 4081")
