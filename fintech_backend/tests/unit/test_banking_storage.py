"""
Beneficiaries, Plaid data and bank transfers on real database storage.

Plaid itself is replaced by a fake here. These tests cover this app's behaviour
around Plaid, not whether Plaid's API accepts the requests.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_banking_storage.py --noconftest --import-mode=importlib
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database.config import Base
from app.database import banking_models  # noqa: F401 - registers the tables
from app.database.models import User
from app.models.plaid import PlaidExchangeTokenRequest, PlaidConnectionPublic
from app.models.transfer import (
    BeneficiaryCreateRequest, TransferCancelRequest, TransferInitiateRequest, TransferQuoteRequest, TransferType
)
from app.core.exceptions import NotFoundError, ValidationError, ExternalServiceException
from app.repositories import banking_repository
from app.repositories.mock_repository import RepositoryManager
from app.services import plaid_service as plaid_service_module
from app.services import plaid_transfer_service as transfer_module
from app.services import transfer_service as money_module
from app.utils import validators


class FakePlaid:
    configured = True

    def __init__(self):
        self.debits = []
        self.fail_next_debit = False
        self.cancelled = []
        self.remote_status = "settled"

    async def exchange_public_token(self, public_token):
        return {"access_token": "access-secret-token", "item_id": f"item-{public_token}"}

    async def get_item(self, access_token):
        return {"institution_id": "ins_1"}

    async def get_institution(self, institution_id):
        return {"name": "First Test Bank"}

    async def get_accounts(self, access_token):
        return [{
            "account_id": "acct-1",
            "name": "Everyday",
            "type": "depository",
            "subtype": "checking",
            "mask": "0000",
            "balances": {"available": 500.0, "current": 500.0, "iso_currency_code": "USD"},
        }]

    async def get_transactions(self, access_token, start_date, end_date):
        return [{
            "transaction_id": "txn-1",
            "account_id": "acct-1",
            "amount": 42.5,
            "iso_currency_code": "USD",
            "date": str(datetime.utcnow().date()),
            "name": "Coffee Shop",
            "pending": False,
        }]

    async def create_transfer(self, data):
        if self.fail_next_debit:
            raise Exception("declined")
        self.debits.append(data)
        return {"transfer_id": f"plaid-{len(self.debits)}", "status": "pending"}

    async def get_transfer_status(self, transfer_id):
        return {"transfer_id": transfer_id, "status": self.remote_status}

    async def cancel_transfer(self, transfer_id):
        self.cancelled.append(transfer_id)
        return {"transfer_id": transfer_id, "status": "cancelled"}

    async def remove_item(self, access_token):
        return {"removed": True}


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(banking_repository, "SessionLocal", Session)
    import app.database.config as db_config
    monkeypatch.setattr(db_config, "SessionLocal", Session)

    fake = FakePlaid()
    monkeypatch.setattr(plaid_service_module, "get_plaid_client", lambda: fake)
    monkeypatch.setattr(transfer_module, "get_plaid_client", lambda: fake)
    monkeypatch.delenv("ENABLE_PLAID_TRANSFERS", raising=False)

    users = {}
    with Session() as db:
        for name in ("ada", "ben"):
            user_id = str(uuid.uuid4())
            db.add(User(
                id=user_id, email=f"{name}@example.com", first_name=name.title(), last_name="Tester",
                password_hash="x"
            ))
            users[name] = user_id
        db.commit()

    return {"engine": engine, "users": users, "plaid": fake}


def run(coro):
    return asyncio.run(coro)


def beneficiary_request(**overrides):
    values = dict(
        beneficiary_type="individual", first_name="Sam", last_name="Payee", address_line1="1 Main St",
        city="Accra", postal_code="00233", country="GH", bank_name="Test Bank", account_number="1234567890",
    )
    return BeneficiaryCreateRequest(**{**values, **overrides})


def link_bank(user_id, token="tok"):
    service = plaid_service_module.PlaidService()
    return run(service.exchange_public_token(user_id, PlaidExchangeTokenRequest(public_token=token)))


def quote_request(beneficiary_id, amount="100.00"):
    return TransferQuoteRequest(
        source_account_id="acct-1", beneficiary_id=beneficiary_id, source_amount=Decimal(amount),
        source_currency="USD", destination_currency="USD", transfer_type=TransferType.PLAID_TRANSFER,
    )


def prepared_quote(user_id, amount="100.00"):
    link_bank(user_id)
    money = money_module.MoneyTransferService()
    beneficiary = run(money.create_beneficiary(user_id, beneficiary_request()))
    quote = run(money.get_transfer_quote(user_id, quote_request(beneficiary.beneficiary_id, amount)))["quote"]
    return money, quote


def initiate_request():
    return TransferInitiateRequest(quote_id="unused", purpose="Rent")


def raw_values(engine, table):
    with engine.connect() as conn:
        return " ".join(str(v) for row in conn.execute(text(f"SELECT * FROM {table}")) for v in row)


# Beneficiaries
def test_beneficiaries_survive_a_restart(env):
    ada = env["users"]["ada"]
    created = run(money_module.MoneyTransferService().create_beneficiary(ada, beneficiary_request()))

    # A new manager has no shared memory with the old one, like a restarted server
    assert run(RepositoryManager().get_beneficiary_by_id(created.beneficiary_id)).first_name == "Sam"


def test_beneficiary_account_number_is_encrypted_and_masked(env):
    ada = env["users"]["ada"]
    money = money_module.MoneyTransferService()
    created = run(money.create_beneficiary(ada, beneficiary_request()))

    assert created.account_number == "****7890"
    assert run(money.list_beneficiaries(ada))["beneficiaries"][0].account_number == "****7890"
    assert "1234567890" not in raw_values(env["engine"], "bank_beneficiaries")
    assert run(RepositoryManager().get_beneficiary_by_id(created.beneficiary_id)).account_number == "1234567890"


def test_new_users_have_no_beneficiaries(env):
    result = run(money_module.MoneyTransferService().list_beneficiaries(env["users"]["ada"]))
    assert result["beneficiaries"] == [] and result["total_count"] == 0


def test_users_cannot_see_or_change_each_others_beneficiaries(env):
    money = money_module.MoneyTransferService()
    created = run(money.create_beneficiary(env["users"]["ada"], beneficiary_request()))

    assert run(money.list_beneficiaries(env["users"]["ben"]))["total_count"] == 0
    with pytest.raises(Exception):
        run(money.delete_beneficiary(env["users"]["ben"], created.beneficiary_id))
    assert run(RepositoryManager().get_beneficiary_by_id(created.beneficiary_id)) is not None


def test_deleting_a_beneficiary_removes_it(env):
    ada = env["users"]["ada"]
    money = money_module.MoneyTransferService()
    created = run(money.create_beneficiary(ada, beneficiary_request()))
    run(money.delete_beneficiary(ada, created.beneficiary_id))
    assert run(money.list_beneficiaries(ada))["total_count"] == 0


# Plaid data
def test_linking_a_bank_stores_accounts_and_transactions(env):
    ada = env["users"]["ada"]
    link = link_bank(ada)
    repo = RepositoryManager()

    assert not hasattr(link, "access_token")
    assert [a.account_id for a in run(repo.get_plaid_accounts(link.connection_id))] == ["acct-1"]
    today = datetime.utcnow().date()
    transactions = run(repo.get_plaid_transactions_by_date_range(link.connection_id, today, today))
    assert [t.name for t in transactions] == ["Coffee Shop"]


def test_access_token_is_encrypted_and_not_in_public_model(env):
    link_bank(env["users"]["ada"])
    assert "access-secret-token" not in raw_values(env["engine"], "plaid_connections")
    assert "access_token" not in PlaidConnectionPublic.model_fields


def test_relinking_a_bank_does_not_duplicate_it(env):
    ada = env["users"]["ada"]
    first = link_bank(ada)
    second = link_bank(ada)
    assert first.connection_id == second.connection_id
    assert len(run(plaid_service_module.PlaidService().get_user_connections(ada))) == 1


def test_a_bank_link_cannot_move_to_another_user(env):
    link_bank(env["users"]["ada"])
    with pytest.raises(ExternalServiceException):
        link_bank(env["users"]["ben"])


def test_stored_accounts_are_returned_when_plaid_is_down(env, monkeypatch):
    ada = env["users"]["ada"]
    link_bank(ada)
    service = plaid_service_module.PlaidService()

    async def down(*args, **kwargs):
        raise Exception("plaid down")

    monkeypatch.setattr(env["plaid"], "get_accounts", down)
    assert [a.account_id for a in run(service.get_user_accounts(ada))] == ["acct-1"]


def test_connection_data_is_private_to_its_owner(env):
    link = link_bank(env["users"]["ada"])
    service = plaid_service_module.PlaidService()
    with pytest.raises(NotFoundError):
        run(service.get_connection_accounts(env["users"]["ben"], link.connection_id))
    with pytest.raises(NotFoundError):
        run(service.get_connection_transactions(env["users"]["ben"], link.connection_id))


# Quotes
def test_quote_rejects_someone_elses_account_and_beneficiary(env):
    ada, ben = env["users"]["ada"], env["users"]["ben"]
    money, _ = prepared_quote(ada)
    ben_beneficiary = run(money.create_beneficiary(ben, beneficiary_request()))
    ada_beneficiary = run(money.list_beneficiaries(ada))["beneficiaries"][0]

    with pytest.raises(NotFoundError):
        run(money.get_transfer_quote(ben, quote_request(ben_beneficiary.beneficiary_id)))
    with pytest.raises(NotFoundError):
        run(money.get_transfer_quote(ada, quote_request(ben_beneficiary.beneficiary_id)))
    assert ada_beneficiary.user_id == ada


def test_quote_rejects_amounts_over_the_balance(env):
    with pytest.raises(ValidationError):
        prepared_quote(env["users"]["ada"], amount="499.00")


def test_only_plaid_transfers_can_be_quoted(env):
    request = quote_request("any").model_copy(update={"transfer_type": TransferType.DOMESTIC_BANK})
    with pytest.raises(ValidationError):
        run(money_module.MoneyTransferService().get_transfer_quote(env["users"]["ada"], request))


# Moving money
def test_transfers_are_off_by_default_and_take_no_money(env):
    ada = env["users"]["ada"]
    money, quote = prepared_quote(ada)

    with pytest.raises(ValidationError, match="No money was taken"):
        run(money.initiate_transfer(ada, quote.quote_id, initiate_request()))

    assert env["plaid"].debits == []
    assert run(money.list_transfers(ada))["total_count"] == 0


def test_enabled_transfer_debits_total_cost_as_the_account_holder(env, monkeypatch):
    monkeypatch.setenv("ENABLE_PLAID_TRANSFERS", "true")
    ada = env["users"]["ada"]
    money, quote = prepared_quote(ada)

    transfer = run(money.initiate_transfer(ada, quote.quote_id, initiate_request()))

    assert transfer.status.value == "processing"
    debit = env["plaid"].debits[0]
    assert debit["amount"] == "102.99"
    assert debit["user"]["legal_name"] == "Ada Tester"
    assert debit["access_token"] == "access-secret-token"
    assert run(RepositoryManager().get_transfer_by_id(transfer.transfer_id)).external_reference == "plaid-1"


def test_a_quote_cannot_debit_twice(env, monkeypatch):
    monkeypatch.setenv("ENABLE_PLAID_TRANSFERS", "true")
    ada = env["users"]["ada"]
    money, quote = prepared_quote(ada)

    run(money.initiate_transfer(ada, quote.quote_id, initiate_request()))
    with pytest.raises(ValidationError, match="already been submitted"):
        run(money.initiate_transfer(ada, quote.quote_id, initiate_request()))

    assert len(env["plaid"].debits) == 1


def test_concurrent_requests_on_one_quote_debit_once(env, monkeypatch):
    monkeypatch.setenv("ENABLE_PLAID_TRANSFERS", "true")
    ada = env["users"]["ada"]
    money, quote = prepared_quote(ada)

    async def both():
        return await asyncio.gather(
            money.initiate_transfer(ada, quote.quote_id, initiate_request()),
            money.initiate_transfer(ada, quote.quote_id, initiate_request()),
            return_exceptions=True,
        )

    results = run(both())
    assert sum(1 for r in results if isinstance(r, Exception)) == 1
    assert len(env["plaid"].debits) == 1


def test_someone_else_cannot_use_a_quote(env, monkeypatch):
    monkeypatch.setenv("ENABLE_PLAID_TRANSFERS", "true")
    money, quote = prepared_quote(env["users"]["ada"])
    with pytest.raises(NotFoundError):
        run(money.initiate_transfer(env["users"]["ben"], quote.quote_id, initiate_request()))
    assert env["plaid"].debits == []


def test_expired_quote_is_rejected(env, monkeypatch):
    monkeypatch.setenv("ENABLE_PLAID_TRANSFERS", "true")
    ada = env["users"]["ada"]
    money, quote = prepared_quote(ada)
    with env["engine"].begin() as conn:
        conn.execute(
            text("UPDATE bank_transfer_quotes SET expires_at = :when"),
            {"when": datetime.utcnow() - timedelta(minutes=1)},
        )
    with pytest.raises(ValidationError, match="expired"):
        run(money.initiate_transfer(ada, quote.quote_id, initiate_request()))
    assert env["plaid"].debits == []


def test_failed_debit_is_recorded_and_not_retried_with_the_same_quote(env, monkeypatch):
    monkeypatch.setenv("ENABLE_PLAID_TRANSFERS", "true")
    ada = env["users"]["ada"]
    money, quote = prepared_quote(ada)
    env["plaid"].fail_next_debit = True

    with pytest.raises(ExternalServiceException):
        run(money.initiate_transfer(ada, quote.quote_id, initiate_request()))

    transfers = run(money.list_transfers(ada))["transfers"]
    assert [t.status.value for t in transfers] == ["failed"]
    env["plaid"].fail_next_debit = False
    with pytest.raises(ValidationError):
        run(money.initiate_transfer(ada, quote.quote_id, initiate_request()))


def test_daily_limit_blocks_going_over(env, monkeypatch):
    monkeypatch.setenv("ENABLE_PLAID_TRANSFERS", "true")
    monkeypatch.setattr(transfer_module, "DAILY_TRANSFER_LIMIT", Decimal("150"))
    ada = env["users"]["ada"]
    money, quote = prepared_quote(ada)
    run(money.initiate_transfer(ada, quote.quote_id, initiate_request()))

    beneficiary = run(money.list_beneficiaries(ada))["beneficiaries"][0]
    second = run(money.get_transfer_quote(ada, quote_request(beneficiary.beneficiary_id)))["quote"]
    with pytest.raises(ValidationError, match="daily limit"):
        run(money.initiate_transfer(ada, second.quote_id, initiate_request()))
    assert len(env["plaid"].debits) == 1


def test_status_updates_from_plaid_are_saved(env, monkeypatch):
    monkeypatch.setenv("ENABLE_PLAID_TRANSFERS", "true")
    ada = env["users"]["ada"]
    money, quote = prepared_quote(ada)
    transfer = run(money.initiate_transfer(ada, quote.quote_id, initiate_request()))

    status = run(money.track_transfer(ada, transfer.transfer_id))

    assert status["status"] == "completed"
    saved = run(RepositoryManager().get_transfer_by_id(transfer.transfer_id))
    assert saved.status.value == "completed" and saved.completed_at is not None
    assert [h["status"] for h in saved.status_history] == ["pending", "processing", "completed"]


def test_cancel_goes_through_plaid(env, monkeypatch):
    monkeypatch.setenv("ENABLE_PLAID_TRANSFERS", "true")
    ada = env["users"]["ada"]
    money, quote = prepared_quote(ada)
    transfer = run(money.initiate_transfer(ada, quote.quote_id, initiate_request()))

    cancelled = run(money.cancel_transfer(ada, transfer.transfer_id, TransferCancelRequest(reason="Changed my mind")))

    assert cancelled.status.value == "cancelled"
    assert env["plaid"].cancelled == ["plaid-1"]


def test_failed_cancel_stays_uncancelled(env, monkeypatch):
    monkeypatch.setenv("ENABLE_PLAID_TRANSFERS", "true")
    ada = env["users"]["ada"]
    money, quote = prepared_quote(ada)
    transfer = run(money.initiate_transfer(ada, quote.quote_id, initiate_request()))

    async def refuse(transfer_id):
        raise Exception("too late")

    monkeypatch.setattr(env["plaid"], "cancel_transfer", refuse)
    with pytest.raises(ExternalServiceException):
        run(money.cancel_transfer(ada, transfer.transfer_id, TransferCancelRequest(reason="Changed my mind")))
    assert run(RepositoryManager().get_transfer_by_id(transfer.transfer_id)).status.value == "processing"


def test_user_validation_finds_database_users(env):
    assert run(validators.validate_user_exists(env["users"]["ada"], RepositoryManager()))
    assert not run(validators.validate_user_exists("nobody", RepositoryManager()))


# Routes
@pytest.fixture
def api(env):
    from fastapi.testclient import TestClient
    from app.auth import dependencies as auth_dependencies
    from app.core import auth as core_auth
    from app.main import app

    current = {"user_id": env["users"]["ada"]}
    app.dependency_overrides[core_auth.get_current_user_id] = lambda: current["user_id"]
    app.dependency_overrides[auth_dependencies.get_current_user_id] = lambda: current["user_id"]
    yield TestClient(app), current
    app.dependency_overrides.clear()


def test_accounts_route_returns_linked_accounts(env, api):
    client, _ = api
    link_bank(env["users"]["ada"])
    response = client.get("/api/v1/accounts/")
    assert response.status_code == 200
    assert [a["account_id"] for a in response.json()["data"]["accounts"]] == ["acct-1"]


def test_transactions_route_returns_synced_transactions(env, api):
    client, _ = api
    link_bank(env["users"]["ada"])
    response = client.get("/api/v1/transactions/?limit=5")
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert [t["name"] for t in body["transactions"]] == ["Coffee Shop"]
    assert body["total_count"] == 1


def test_routes_are_empty_not_errors_without_a_bank(api):
    client, _ = api
    assert client.get("/api/v1/accounts/").json()["data"]["accounts"] == []
    assert client.get("/api/v1/transactions/").json()["data"]["transactions"] == []
    assert client.get("/api/v1/plaid/connections").json() == []
    assert client.get("/api/v1/plaid/accounts").json() == []


def test_account_route_is_private_to_its_owner(env, api):
    client, current = api
    link_bank(env["users"]["ada"])
    current["user_id"] = env["users"]["ben"]
    assert client.get("/api/v1/accounts/").json()["data"]["accounts"] == []
    assert client.get("/api/v1/transactions/").json()["data"]["transactions"] == []


def test_paying_other_banks_is_off_and_takes_no_money(env, api):
    # The /plaid routes now live in bank_links (tested in test_bank_links.py); paying a beneficiary's bank waits for a bank partner
    client, _ = api
    _, quote = prepared_quote(env["users"]["ada"])
    response = client.post(
        "/api/v1/plaid/transfers/initiate", json={"quote_id": quote.quote_id, "purpose": "Rent"}
    )
    assert response.status_code == 503
    assert "isn't available yet" in response.text
    assert env["plaid"].debits == []


def test_beneficiary_is_saved_masked_but_bank_payouts_wait(env, api, monkeypatch):
    monkeypatch.setenv("ENABLE_PLAID_TRANSFERS", "true")
    client, _ = api
    beneficiary = client.post("/api/v1/transfers/beneficiaries", json={
        "beneficiary_type": "individual", "first_name": "Sam", "last_name": "Payee", "address_line1": "1 Main St",
        "city": "Accra", "postal_code": "00233", "country": "GH", "bank_name": "Test Bank",
        "account_number": "1234567890",
    })
    assert beneficiary.status_code == 200, beneficiary.text
    created = beneficiary.json()["data"]["beneficiary"]
    assert created["account_number"] == "****7890"

    quote = client.post("/api/v1/plaid/transfers/quote", json={
        "source_account_id": "acct-1", "beneficiary_id": created["beneficiary_id"], "amount": "50.00",
    })
    assert quote.status_code == 503
    assert env["plaid"].debits == []
