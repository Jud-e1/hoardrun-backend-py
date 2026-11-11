"""
Investment circles: admin-approved joining, one-person-one-vote majorities, and money
taken only from the people who agreed.

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
from app.database.circle_models import CircleInvestment
from app.database.config import Base, get_db
from app.database.models import Account, AccountTypeEnum, User
from app.database.venture_models import VentureFund

CASH = {"ama": "10000", "ben": "10000", "cy": "10000", "dee": "10000", "vc": "0"}


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        for user_id, cash in CASH.items():
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
    circle = client.post("/api/v1/circles", json={
        "name": "Saturday Club", "purpose": "Back early African startups together", "min_contribution": "50",
        "focus": "private_equity", "max_members": 4,
    }).json()["data"]
    return client, current, Session, circle["id"], fund_id


def as_user(client, current, user_id):
    current["user"] = user_id
    return client


def admit(client, current, circle_id, *people):
    """Each person asks to join and Ama, the admin, accepts them."""
    for person in people:
        as_user(client, current, person).post(f"/api/v1/circles/{circle_id}/join", json={"note": "Hi"})
    detail = as_user(client, current, "ama").get(f"/api/v1/circles/{circle_id}").json()["data"]
    for request in detail["requests"]:
        detail = client.post(f"/api/v1/circles/{circle_id}/requests/{request['id']}/approve").json()["data"]
    return detail


def cash(Session, user_id):
    with Session() as db:
        return db.get(Account, f"acct-{user_id}").available_balance


def asset_proposal(client, circle_id, amount="100"):
    return client.post(f"/api/v1/circles/{circle_id}/proposals", json={
        "kind": "asset", "asset_type": "real_estate", "title": "Rental flat in Accra", "amount_per_member": amount,
    })


def test_joining_waits_for_the_admin(env):
    client, current, _, circle_id, _ = env
    asked = as_user(client, current, "ben").post(f"/api/v1/circles/{circle_id}/join", json={"note": "Friend of Ama"}).json()["data"]
    assert asked["my_status"] == "pending"
    assert asked["member_count"] == 1
    # Waiting people can't put money in or vote, and can't answer requests
    assert client.post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "100"}).status_code == 403
    assert client.post(f"/api/v1/circles/{circle_id}/requests/x/approve").status_code == 403

    admin = as_user(client, current, "ama").get(f"/api/v1/circles/{circle_id}").json()["data"]
    assert admin["pending_count"] == 1
    assert admin["requests"][0]["note"] == "Friend of Ama"
    done = client.post(f"/api/v1/circles/{circle_id}/requests/{admin['requests'][0]['id']}/approve").json()["data"]
    assert done["member_count"] == 2 and done["requests"] == []
    assert as_user(client, current, "ben").get(f"/api/v1/circles/{circle_id}").json()["data"]["my_status"] == "member"


def test_declined_and_withdrawn_requests_leave_no_member(env):
    client, current, _, circle_id, _ = env
    as_user(client, current, "ben").post(f"/api/v1/circles/{circle_id}/join")
    request_id = as_user(client, current, "ama").get(f"/api/v1/circles/{circle_id}").json()["data"]["requests"][0]["id"]
    detail = client.post(f"/api/v1/circles/{circle_id}/requests/{request_id}/decline").json()["data"]
    assert detail["member_count"] == 1 and detail["requests"] == []
    assert as_user(client, current, "ben").get(f"/api/v1/circles/{circle_id}").json()["data"]["my_status"] is None

    as_user(client, current, "cy").post(f"/api/v1/circles/{circle_id}/join")
    assert client.delete(f"/api/v1/circles/{circle_id}/join").json()["data"]["my_status"] is None


def test_a_full_circle_takes_no_more_people(env):
    client, current, _, circle_id, _ = env
    admit(client, current, circle_id, "ben", "cy", "dee")
    assert as_user(client, current, "vc").post(f"/api/v1/circles/{circle_id}/join").status_code == 409


def test_one_person_cannot_decide_alone(env):
    client, current, Session, circle_id, _ = env
    detail = asset_proposal(client, circle_id).json()["data"]
    proposal = detail["proposals"][0]
    assert proposal["status"] == "open"
    assert proposal["votes_needed"] == 2
    assert cash(Session, "ama") == Decimal("10000")


def test_majority_yes_invests_and_only_the_yes_voters_pay(env):
    client, current, Session, circle_id, _ = env
    admit(client, current, circle_id, "ben", "cy")
    proposal_id = asset_proposal(as_user(client, current, "ama"), circle_id, "250").json()["data"]["proposals"][0]["id"]

    # 2 of 3 is more than half
    detail = as_user(client, current, "ben").post(f"/api/v1/circles/{circle_id}/proposals/{proposal_id}/vote", json={"choice": "yes"}).json()["data"]
    proposal = detail["proposals"][0]
    assert proposal["status"] == "passed"
    assert proposal["amount"] == 500
    assert proposal["my_paid"] == 250
    assert detail["invested"] == 500
    assert cash(Session, "ama") == Decimal("9750") and cash(Session, "ben") == Decimal("9750")
    assert cash(Session, "cy") == Decimal("10000")
    # Voting has closed for anyone who comes late
    assert as_user(client, current, "cy").post(f"/api/v1/circles/{circle_id}/proposals/{proposal_id}/vote", json={"choice": "yes"}).status_code == 409


def test_half_is_not_a_majority(env):
    client, current, Session, circle_id, _ = env
    admit(client, current, circle_id, "ben", "cy", "dee")
    proposal_id = asset_proposal(as_user(client, current, "ama"), circle_id).json()["data"]["proposals"][0]["id"]
    detail = as_user(client, current, "ben").post(f"/api/v1/circles/{circle_id}/proposals/{proposal_id}/vote", json={"choice": "yes"}).json()["data"]
    assert detail["proposals"][0]["status"] == "open"
    assert detail["proposals"][0]["votes_needed"] == 3
    detail = as_user(client, current, "cy").post(f"/api/v1/circles/{circle_id}/proposals/{proposal_id}/vote", json={"choice": "yes"}).json()["data"]
    assert detail["proposals"][0]["status"] == "passed"
    assert cash(Session, "dee") == Decimal("10000")


def test_majority_no_rejects_and_nobody_pays(env):
    client, current, Session, circle_id, _ = env
    admit(client, current, circle_id, "ben", "cy")
    proposal_id = asset_proposal(as_user(client, current, "ama"), circle_id).json()["data"]["proposals"][0]["id"]
    as_user(client, current, "ben").post(f"/api/v1/circles/{circle_id}/proposals/{proposal_id}/vote", json={"choice": "no"})
    detail = as_user(client, current, "cy").post(f"/api/v1/circles/{circle_id}/proposals/{proposal_id}/vote", json={"choice": "no"}).json()["data"]
    assert detail["proposals"][0]["status"] == "rejected"
    assert cash(Session, "ama") == Decimal("10000")


def test_nobody_is_charged_when_fewer_than_two_agreeing_people_can_pay(env):
    client, current, Session, circle_id, _ = env
    admit(client, current, circle_id, "vc", "ben")
    proposal_id = asset_proposal(as_user(client, current, "ama"), circle_id).json()["data"]["proposals"][0]["id"]
    detail = as_user(client, current, "vc").post(f"/api/v1/circles/{circle_id}/proposals/{proposal_id}/vote", json={"choice": "yes"}).json()["data"]
    assert detail["proposals"][0]["status"] == "failed"
    assert cash(Session, "ama") == Decimal("10000")
    with Session() as db:
        assert db.query(CircleInvestment).count() == 0


def test_pooled_fund_purchase_needs_a_headcount_majority(env):
    client, current, Session, circle_id, fund_id = env
    admit(client, current, circle_id, "ben", "cy")
    as_user(client, current, "ama").post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "300"})
    as_user(client, current, "ben").post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "700"})

    detail = as_user(client, current, "ama").post(f"/api/v1/circles/{circle_id}/proposals", json={"kind": "fund", "fund_id": fund_id, "shares": 5}).json()["data"]
    proposal = detail["proposals"][0]
    assert proposal["status"] == "open"
    detail = as_user(client, current, "cy").post(f"/api/v1/circles/{circle_id}/proposals/{proposal['id']}/vote", json={"choice": "yes"}).json()["data"]
    assert detail["proposals"][0]["status"] == "passed"
    assert detail["pool_balance"] == 500
    with Session() as db:
        assert db.get(VentureFund, fund_id).shares_sold == 5


def test_contributions_and_pool_limits(env):
    client, current, Session, circle_id, fund_id = env
    admit(client, current, circle_id, "ben")
    client = as_user(client, current, "ben")
    detail = client.post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "400"}).json()["data"]
    assert detail["pool_balance"] == 400
    assert cash(Session, "ben") == Decimal("9600")
    assert client.post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "10"}).status_code == 400
    assert client.post(f"/api/v1/circles/{circle_id}/proposals", json={"kind": "fund", "fund_id": fund_id, "shares": 5}).status_code == 400
    outsider = as_user(client, current, "cy").post(f"/api/v1/circles/{circle_id}/contribute", json={"amount": "100"})
    assert outsider.status_code == 403
