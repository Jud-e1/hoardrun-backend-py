"""
Investment circles: pooled cash, weighted votes, and shared ownership.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_circles.py --noconftest --import-mode=importlib
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

from app.api.v1 import circles, venture
from app.auth.dependencies import get_current_user_id
from app.database import circle_models, venture_models  # noqa: F401 - registers the tables
from app.database.config import Base, get_db
from app.database.models import Account, AccountTypeEnum, User
from app.database.venture_models import VentureFund


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        for user_id, cash in (("ama", "10000"), ("ben", "10000"), ("cy", "10000"), ("vc", "0")):
            db.add(User(id=user_id, email=f"{user_id}@example.com", password_hash="x", first_name=user_id.title(), last_name="Test"))
            db.add(Account(id=f"acct-{user_id}", user_id=user_id, account_number=f"ACCT{user_id.upper():0>10}"[:20], account_name="Cash",
                           account_type=AccountTypeEnum.CHECKING, currency="USD", is_primary=True,
                           current_balance=Decimal(cash), available_balance=Decimal(cash)))
        db.commit()

    app = FastAPI()
    app.include_router(circles.router, prefix="/api/v1")
    app.include_router(venture.router, prefix="/api/v1")
    current = {"user": "vc"}

    def session():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user_id] = lambda: current["user"]
    client = TestClient(app)

    fund_id = client.post("/api/v1/venture-funds", json={
        "firm_name": "Harbor Ventures", "fund_name": "Harbor Seed Fund I", "thesis": "Seed rounds in African fintech",
        "sectors": ["Fintech"], "stage": "seed", "share_price": "100", "total_shares": 1000, "min_shares": 1,
        "term_years": 8, "management_fee": "2", "carry": "20",
    }).json()["data"]["id"]
    current["user"] = "ama"
    circle = client.post("/api/v1/circles", json={"name": "Saturday Club", "purpose": "Back early African startups together", "min_contribution": "50"}).json()["data"]
    return client, current, Session, circle["id"], fund_id


def as_user(client, current, user_id):
    current["user"] = user_id
    return client


def test_contributions_set_each_members_share(env):
    client, current, Session, circle_id, _ = env
    client.post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "600"})
    as_user(client, current, "ben").post(f"/api/v1/circles/{circle_id}/join")
    detail = client.post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "400"}).json()["data"]
    assert detail["pool_balance"] == 1000
    assert detail["my_share"] == pytest.approx(0.4)
    assert [m["share"] for m in detail["members"]] == [pytest.approx(0.6), pytest.approx(0.4)]
    with Session() as db:
        assert db.get(Account, "acct-ben").available_balance == Decimal("9600.00")

    too_small = client.post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "10"})
    assert too_small.status_code == 400
    outsider = as_user(client, current, "cy").post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "100"})
    assert outsider.status_code == 403


def test_biggest_contributor_decides_and_shares_are_split(env):
    client, current, Session, circle_id, fund_id = env
    client.post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "300"})
    as_user(client, current, "ben").post(f"/api/v1/circles/{circle_id}/join")
    client.post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "700"})

    # Ama holds 30%: her proposal (and automatic yes) is not enough on its own
    detail = as_user(client, current, "ama").post(f"/api/v1/circles/{circle_id}/proposals", json={"fund_id": fund_id, "shares": 5}).json()["data"]
    proposal = detail["proposals"][0]
    assert proposal["status"] == "open"
    assert proposal["yes"] == pytest.approx(0.3)

    # Ben holds 70%, so his yes buys the shares from the pool
    detail = as_user(client, current, "ben").post(f"/api/v1/circles/{circle_id}/proposals/{proposal['id']}/vote", json={"choice": "yes"}).json()["data"]
    assert detail["proposals"][0]["status"] == "passed"
    assert detail["pool_balance"] == 500
    holding = detail["holdings"][0]
    assert holding["shares"] == 5
    assert holding["my_shares"] == pytest.approx(3.5)
    with Session() as db:
        assert db.get(VentureFund, fund_id).shares_sold == 5


def test_majority_no_rejects_and_closed_votes_stay_closed(env):
    client, current, _, circle_id, fund_id = env
    client.post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "400"})
    as_user(client, current, "ben").post(f"/api/v1/circles/{circle_id}/join")
    client.post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "600"})
    proposal_id = as_user(client, current, "ama").post(f"/api/v1/circles/{circle_id}/proposals", json={"fund_id": fund_id, "shares": 2}).json()["data"]["proposals"][0]["id"]
    detail = as_user(client, current, "ben").post(f"/api/v1/circles/{circle_id}/proposals/{proposal_id}/vote", json={"choice": "no"}).json()["data"]
    assert detail["proposals"][0]["status"] == "rejected"
    assert detail["pool_balance"] == 1000
    assert client.post(f"/api/v1/circles/{circle_id}/proposals/{proposal_id}/vote", json={"choice": "yes"}).status_code == 409


def test_proposals_cannot_spend_more_than_the_pool(env):
    client, _, _, circle_id, fund_id = env
    client.post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "250"})
    assert client.post(f"/api/v1/circles/{circle_id}/proposals", json={"fund_id": fund_id, "shares": 3}).status_code == 400
    # A sole member owns 100%, so their proposal passes straight away
    detail = client.post(f"/api/v1/circles/{circle_id}/proposals", json={"fund_id": fund_id, "shares": 2}).json()["data"]
    assert detail["proposals"][0]["status"] == "passed"
    assert detail["pool_balance"] == 50
