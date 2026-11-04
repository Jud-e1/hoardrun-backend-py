"""
Hoardrun AI chat route. Claude is replaced by a fake client, so no request leaves the machine.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_assistant.py --noconftest --import-mode=importlib
"""

import os
from decimal import Decimal
from types import SimpleNamespace

# Must be set before the app is imported, so these tests can never reach a real database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import assistant
from app.auth.dependencies import get_current_user_id
from app.database.config import Base, get_db
from app.database.market_models import MarketPosition
from app.database.models import Account, AccountTypeEnum, User


class FakeMessages:
    def __init__(self, reply="Here's a plan. [Open Savings](/savings)", stop_reason="end_turn"):
        self.calls = []
        self.reply = reply
        self.stop_reason = stop_reason

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="text", text=self.reply)],
        )


def fake_client(messages):
    return SimpleNamespace(beta=SimpleNamespace(messages=messages))


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(User(id="ada", email="ada@example.com", password_hash="x", first_name="Ada", last_name="Mensah"))
        db.add(User(id="kofi", email="kofi@example.com", password_hash="x", first_name="Kofi", last_name="Boateng"))
        db.add(Account(id="acct-ada", user_id="ada", account_number="ACCTADA0000001", account_name="Cash (USD)",
                       account_type=AccountTypeEnum.CHECKING, currency="USD", is_primary=True,
                       current_balance=Decimal("1250.50"), available_balance=Decimal("1250.50")))
        db.add(Account(id="acct-kofi", user_id="kofi", account_number="ACCTKOFI000001", account_name="Kofi cash",
                       account_type=AccountTypeEnum.CHECKING, currency="USD",
                       current_balance=Decimal("99999"), available_balance=Decimal("99999")))
        db.add(MarketPosition(id="pos-1", user_id="ada", asset_type="crypto", symbol="BTC",
                              quantity=Decimal("0.01"), cost_basis=Decimal("600")))
        db.commit()

    app = FastAPI()
    app.include_router(assistant.router, prefix="/api/v1")

    def db_override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user_id] = lambda: "ada"
    messages = FakeMessages()
    monkeypatch.setattr(assistant, "get_client", lambda: fake_client(messages))
    return TestClient(app), messages


def test_reply_uses_the_users_own_numbers(env):
    client, messages = env
    response = client.post("/api/v1/assistant/chat", json={"messages": [{"role": "user", "content": "How am I doing?"}]})

    assert response.status_code == 200
    assert response.json()["reply"].startswith("Here's a plan")
    call = messages.calls[0]
    snapshot = call["system"][1]["text"]
    assert "$1,250.50" in snapshot and "BTC" in snapshot and "Ada" in snapshot
    # Another person's money never reaches the prompt
    assert "99,999" not in snapshot and "Kofi" not in snapshot
    assert call["model"] == "claude-opus-5-5"
    assert call["fallbacks"] == "default"


def test_history_is_trimmed_to_open_with_the_user(env):
    client, messages = env
    history = [{"role": "assistant", "content": "Hi, I'm Hoardrun AI."}, {"role": "user", "content": "Help me save"}]
    response = client.post("/api/v1/assistant/chat", json={"messages": history})

    assert response.status_code == 200
    assert [m["role"] for m in messages.calls[0]["messages"]] == ["user"]


def test_last_turn_must_be_the_user(env):
    client, _ = env
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
    assert client.post("/api/v1/assistant/chat", json={"messages": history}).status_code == 400


def test_refusal_gets_a_friendly_answer(env, monkeypatch):
    client, _ = env
    monkeypatch.setattr(assistant, "get_client", lambda: fake_client(FakeMessages(reply="", stop_reason="refusal")))
    response = client.post("/api/v1/assistant/chat", json={"messages": [{"role": "user", "content": "x"}]})
    assert response.status_code == 200
    assert "can't help with that" in response.json()["reply"]


def test_without_a_key_it_says_so(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(assistant, "_client", None)
    monkeypatch.setitem(__import__("sys").modules, "dotenv", None)
    with pytest.raises(Exception) as error:
        assistant.get_client()
    assert getattr(error.value, "status_code", None) == 503
