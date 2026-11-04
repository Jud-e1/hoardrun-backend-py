"""
Linked banks through Plaid and ACH to and from Hoardrun cash. Plaid itself is faked.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_bank_links.py --noconftest --import-mode=importlib
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

from app.api.v1 import bank_links
from app.auth.dependencies import get_current_user_id
from app.database.config import Base, get_db
from app.database.models import Account, Transaction, TransactionStatusEnum, TransactionTypeEnum, User
from app.services import sealed
from app.services.deposit_ledger import cash_account
from app.services.inbox import Notification
from app.services.plaid_gateway import PlaidError

ACCESS = "access-sandbox-secret-token"


class FakePlaid:
    def __init__(self):
        self.events_feed = []
        self.transfers = []
        self.removed = []
        self.decision = "approved"
        self.item_id = "item-1"

    def link_token(self, user_id, webhook=None, access_token=None):
        return {"link_token": "link-sandbox-1", "expiration": "2026-11-04T10:00:00Z"}

    def exchange(self, public_token):
        return {"access_token": ACCESS, "item_id": self.item_id}

    def item(self, access_token):
        return {"item_id": self.item_id, "institution_id": "ins_1", "institution_name": "First Platypus Bank", "error_code": None}

    def accounts(self, access_token):
        assert access_token == ACCESS
        return [{"account_id": "acc-checking", "name": "Plaid Checking", "official_name": None, "mask": "0000",
                 "type": "depository", "subtype": "checking", "available": 100.0, "current": 110.0, "limit": None,
                 "currency": "USD"}]

    def transactions(self, access_token, start, end, count=100):
        return [{"transaction_id": "t1", "account_id": "acc-checking", "amount": 12.5, "currency": "USD",
                 "date": str(end), "name": "Coffee", "merchant_name": "Cafe", "pending": False, "category": []}]

    def remove(self, access_token):
        self.removed.append(access_token)

    def authorize(self, **kwargs):
        return {"id": "auth-1", "decision": self.decision, "reason": "Insufficient funds" if self.decision != "approved" else None}

    def create_transfer(self, **kwargs):
        transfer_id = f"plaid-tr-{len(self.transfers) + 1}"
        self.transfers.append({"id": transfer_id, **kwargs})
        return {"id": transfer_id, "status": "pending"}

    def push(self, transfer_id, event_type, reason=None):
        self.events_feed.append({"event_id": len(self.events_feed) + 1, "transfer_id": transfer_id,
                                 "event_type": event_type, "failure_reason": reason})

    def events(self, after_id, count=25):
        return [e for e in self.events_feed if e["event_id"] > after_id][:count]


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(User(id="ada", email="ada@example.com", password_hash="x", first_name="Ada", last_name="Mensah"))
        db.add(User(id="kofi", email="kofi@example.com", password_hash="x", first_name="Kofi", last_name="Boateng"))
        db.commit()

    fake = FakePlaid()
    monkeypatch.setattr(bank_links, "get_gateway", lambda: fake)
    monkeypatch.setattr(sealed, "_fernet", None)
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "k" * 40)

    app = FastAPI()
    app.include_router(bank_links.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    who = {"id": "ada"}
    app.dependency_overrides[get_current_user_id] = lambda: who["id"]
    yield TestClient(app), Session, fake, who
    sealed._fernet = None


def link(client):
    response = client.post("/api/v1/plaid/exchange-token", json={"public_token": "public-sandbox-123"})
    assert response.status_code == 200, response.text
    return response.json()


def cash(Session, user="ada"):
    with Session() as db:
        return sum((Decimal(a.available_balance) for a in db.query(Account).filter(Account.user_id == user)), Decimal(0))


def give_cash(Session, amount, user="ada"):
    with Session() as db:
        account = cash_account(db, user, "USD")
        account.available_balance = account.current_balance = Decimal(amount)
        db.commit()


def sync(client):
    assert client.post("/api/v1/plaid/transfers/sync").status_code == 200


def test_linking_keeps_the_access_token_encrypted_and_out_of_the_browser(env):
    client, Session, _, _ = env
    body = link(client)
    assert "access_token" not in body and ACCESS not in str(body)
    assert body["institution_name"] == "First Platypus Bank" and body["accounts"][0]["mask"] == "0000"
    with Session() as db:
        stored = db.query(bank_links.BankLink).one()
        assert stored.access_token != ACCESS and sealed.unseal(stored.access_token) == ACCESS
    accounts = client.get("/api/v1/plaid/accounts").json()
    assert accounts[0]["balances"]["available"] == 100.0
    assert client.get("/api/v1/plaid/connections").json()[0]["status"] == "active"


def test_a_bank_linked_to_someone_else_is_refused(env):
    client, _, _, who = env
    link(client)
    who["id"] = "kofi"
    assert client.post("/api/v1/plaid/exchange-token", json={"public_token": "public-sandbox-123"}).status_code == 409
    assert client.get("/api/v1/plaid/accounts").json() == []


def test_bank_deposit_adds_cash_once_it_settles_and_only_once(env):
    client, Session, fake, _ = env
    link(client)
    transfer = client.post("/api/v1/plaid/transfers/deposit", json={"account_id": "acc-checking", "amount": 40}).json()
    assert transfer["status"] == "pending" and cash(Session) == 0
    assert fake.transfers[0]["description"] == "Hoardrun"

    fake.push("plaid-tr-1", "posted")
    sync(client)
    assert cash(Session) == 0
    fake.push("plaid-tr-1", "settled")
    fake.push("plaid-tr-1", "funds_available")
    sync(client)
    sync(client)
    assert cash(Session) == Decimal("40")
    with Session() as db:
        assert db.query(Transaction).filter(Transaction.transaction_type == TransactionTypeEnum.DEPOSIT).count() == 1
        titles = [n.title for n in db.query(Notification).all()]
        assert titles.count("Money added") == 1


def test_failed_deposit_adds_nothing_and_a_late_return_takes_it_back(env):
    client, Session, fake, _ = env
    link(client)
    client.post("/api/v1/plaid/transfers/deposit", json={"account_id": "acc-checking", "amount": 25})
    fake.push("plaid-tr-1", "failed", "Account closed")
    sync(client)
    assert cash(Session) == 0
    history = client.get("/api/v1/plaid/transfers/history").json()["transfers"]
    assert history[0]["status"] == "failed" and history[0]["failure_reason"] == "Account closed"

    client.post("/api/v1/plaid/transfers/deposit", json={"account_id": "acc-checking", "amount": 30})
    fake.push("plaid-tr-2", "settled")
    sync(client)
    assert cash(Session) == Decimal("30")
    fake.push("plaid-tr-2", "returned", "Not authorized")
    sync(client)
    assert cash(Session) == 0


def test_withdrawal_takes_cash_now_and_refunds_it_if_returned(env):
    client, Session, fake, _ = env
    link(client)
    give_cash(Session, 100)
    first = client.post("/api/v1/plaid/transfers/withdraw", json={"account_id": "acc-checking", "amount": 60}).json()
    assert cash(Session) == Decimal("40")
    with Session() as db:
        entry = db.query(Transaction).filter(Transaction.reference_number == first["reference"] + "-OUT").one()
        assert entry.status == TransactionStatusEnum.PENDING
    fake.push("plaid-tr-1", "settled")
    sync(client)
    with Session() as db:
        assert db.query(Transaction).filter(Transaction.reference_number == first["reference"] + "-OUT").one().status == TransactionStatusEnum.COMPLETED

    client.post("/api/v1/plaid/transfers/withdraw", json={"account_id": "acc-checking", "amount": 40})
    assert cash(Session) == 0
    fake.push("plaid-tr-2", "returned", "Account frozen")
    sync(client)
    sync(client)
    assert cash(Session) == Decimal("40")


def test_withdrawal_needs_the_cash_and_plaid_is_never_asked_otherwise(env):
    client, Session, fake, _ = env
    link(client)
    give_cash(Session, 10)
    response = client.post("/api/v1/plaid/transfers/withdraw", json={"account_id": "acc-checking", "amount": 50})
    assert response.status_code == 402 and fake.transfers == [] and cash(Session) == Decimal("10")


def test_declined_withdrawal_leaves_the_cash_alone(env):
    client, Session, fake, _ = env
    link(client)
    give_cash(Session, 100)
    fake.decision = "declined"
    response = client.post("/api/v1/plaid/transfers/withdraw", json={"account_id": "acc-checking", "amount": 50})
    assert response.status_code == 400 and "Insufficient funds" in response.json()["detail"]
    assert cash(Session) == Decimal("100") and fake.transfers == []
    with Session() as db:
        assert db.query(bank_links.BankTransfer).count() == 0


def test_limits_and_other_peoples_accounts(env):
    client, _, _, who = env
    link(client)
    assert client.post("/api/v1/plaid/transfers/deposit", json={"account_id": "acc-checking", "amount": 0.5}).status_code == 400
    assert client.post("/api/v1/plaid/transfers/deposit", json={"account_id": "acc-checking", "amount": 20000}).status_code == 400
    who["id"] = "kofi"
    assert client.post("/api/v1/plaid/transfers/deposit", json={"account_id": "acc-checking", "amount": 20}).status_code == 404


def test_webhook_body_is_never_trusted(env):
    client, Session, fake, _ = env
    link(client)
    client.post("/api/v1/plaid/transfers/deposit", json={"account_id": "acc-checking", "amount": 40})
    # A forged webhook claiming the deposit settled: Plaid's own feed says nothing happened
    forged = {"webhook_type": "TRANSFER", "webhook_code": "TRANSFER_EVENTS_UPDATE", "transfer_id": "plaid-tr-1", "event_type": "settled"}
    assert client.post("/api/v1/plaid/webhook", json=forged).status_code == 200
    assert cash(Session) == 0
    fake.push("plaid-tr-1", "settled")
    client.post("/api/v1/plaid/webhook", json={"webhook_type": "TRANSFER"})
    assert cash(Session) == Decimal("40")


def test_unlinking_tells_plaid_and_keeps_transfer_history(env):
    client, Session, fake, _ = env
    body = link(client)
    client.post("/api/v1/plaid/transfers/deposit", json={"account_id": "acc-checking", "amount": 15})
    assert client.delete(f"/api/v1/plaid/connections/{body['connection_id']}").status_code == 200
    assert fake.removed == [ACCESS]
    assert client.get("/api/v1/plaid/accounts").json() == []
    assert len(client.get("/api/v1/plaid/transfers/history").json()["transfers"]) == 1


def test_bank_transactions_and_paying_other_banks(env):
    client, _, _, _ = env
    body = link(client)
    rows = client.get(f"/api/v1/plaid/connections/{body['connection_id']}/transactions").json()
    assert rows[0]["name"] == "Coffee" and rows[0]["connection_id"] == body["connection_id"]
    response = client.post("/api/v1/plaid/transfers/quote", json={})
    assert response.status_code == 503 and "isn't available yet" in response.json()["detail"]


def test_not_configured_says_so(env, monkeypatch):
    client, _, _, _ = env
    settings = bank_links.get_settings()
    monkeypatch.setattr(settings, "plaid_client_id", "")
    monkeypatch.setattr(settings, "plaid_secret", "")
    monkeypatch.setattr(bank_links, "get_gateway", REAL_GET_GATEWAY)
    assert client.get("/api/v1/plaid/status").json()["configured"] is False
    response = client.post("/api/v1/plaid/link-token", json={})
    assert response.status_code == 503 and response.json()["detail"] == "Bank linking isn't set up yet"


def test_production_refuses_to_store_tokens_without_a_key(monkeypatch):
    monkeypatch.setattr(sealed, "_fernet", None)
    monkeypatch.delenv("DATA_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(sealed.get_settings(), "data_encryption_key", "")
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(sealed.SealError):
        sealed.seal("secret")
    sealed._fernet = None


REAL_GET_GATEWAY = bank_links.get_gateway


def test_account_cannot_close_while_a_bank_transfer_is_on_the_way(env):
    from app.api.v1.account_lifecycle import blockers
    client, Session, fake, _ = env
    link(client)
    client.post("/api/v1/plaid/transfers/deposit", json={"account_id": "acc-checking", "amount": 20})
    with Session() as db:
        assert any("bank transfer" in reason for reason in blockers(db, "ada"))
    fake.push("plaid-tr-1", "failed")
    sync(client)
    with Session() as db:
        assert blockers(db, "ada") == []
