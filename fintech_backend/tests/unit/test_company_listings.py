"""
Business listings: admin review before they go public, investing in approved ones, and
the admin area that reviews them.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_company_listings.py --noconftest --import-mode=importlib
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

from app.api.v1 import admin_panel, opportunities
from app.auth.dependencies import get_current_user_id
from app.database import registry  # noqa: F401 - registers every table
from app.database.config import Base, get_db
from app.database.models import Account, AccountTypeEnum, User
from app.services.inbox import Notification


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PLATFORM_ADMIN_EMAILS", "Owner@Example.com")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        for user_id, cash in (("alice", "0"), ("bob", "5000"), ("owner", "0")):
            db.add(User(id=user_id, email=f"{user_id}@example.com", password_hash="x", first_name=user_id.title(), last_name="Test", email_verified=True))
            db.add(Account(id=f"acct-{user_id}", user_id=user_id, account_number=f"ACCT{user_id.upper():0>10}"[:20], account_name="Cash",
                           account_type=AccountTypeEnum.CHECKING, currency="USD", is_primary=True,
                           current_balance=Decimal(cash), available_balance=Decimal(cash)))
        db.commit()

    app = FastAPI()
    app.include_router(opportunities.router, prefix="/api/v1")
    app.include_router(admin_panel.router, prefix="/api/v1")
    current = {"user": "alice"}

    def session():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user_id] = lambda: current["user"]
    test_client = TestClient(app)
    test_client.current = current
    test_client.Session = Session
    return test_client


def company(**overrides):
    body = {
        "name": "Northwind Labs",
        "category": "private-equity",
        "sector": "Logistics software",
        "tagline": "Route planning for small delivery fleets",
        "location": "Accra, Ghana",
        "website": "northwind.example",
        "founded_year": 2021,
        "funding_goal": "5000",
        "min_investment": "1000",
        "target_return": "15-20%",
        "risk_level": "high",
    }
    body.update(overrides)
    return body


def as_user(client, user_id):
    client.current["user"] = user_id
    return client


def listed_and_approved(client, **overrides):
    listing_id = as_user(client, "alice").post("/api/v1/opportunities", json=company(**overrides)).json()["data"]["id"]
    assert as_user(client, "owner").post(f"/api/v1/admin-panel/listings/{listing_id}/approve").status_code == 200
    return listing_id


def test_empty_until_a_company_is_listed(client):
    response = client.get("/api/v1/opportunities?category=private-equity")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_a_new_listing_waits_for_review_and_only_its_owner_sees_it(client):
    created = client.post("/api/v1/opportunities", json=company())
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["review_status"] == "pending"
    assert data["website"] == "https://northwind.example"
    assert data["can_invest"] is False
    assert client.get("/api/v1/opportunities?category=private-equity").json()["total"] == 1

    bob = as_user(client, "bob")
    assert bob.get("/api/v1/opportunities?category=private-equity").json()["total"] == 0
    assert bob.get(f"/api/v1/opportunities/{data['id']}").status_code == 404
    assert bob.post(f"/api/v1/opportunities/{data['id']}/invest", json={"amount": "1000"}).status_code == 404


def test_approval_puts_it_on_its_page_and_tells_the_owner(client):
    listing_id = listed_and_approved(client, category="real-estate")
    bob = as_user(client, "bob")
    assert bob.get("/api/v1/opportunities?category=real-estate").json()["total"] == 1
    assert bob.get("/api/v1/opportunities?category=private-equity").json()["total"] == 0
    assert bob.get(f"/api/v1/opportunities/{listing_id}").json()["data"]["can_invest"] is True
    with client.Session() as db:
        assert db.query(Notification).filter_by(user_id="alice").first().title == "Northwind Labs is live"


def test_a_rejected_listing_stays_private_with_the_reason_for_its_owner(client):
    listing_id = client.post("/api/v1/opportunities", json=company()).json()["data"]["id"]
    as_user(client, "owner").post(f"/api/v1/admin-panel/listings/{listing_id}/reject", json={"note": "Add your registration number"})
    assert as_user(client, "bob").get("/api/v1/opportunities").json()["total"] == 0
    mine = as_user(client, "alice").get(f"/api/v1/opportunities/{listing_id}").json()["data"]
    assert mine["review_status"] == "rejected"
    assert mine["review_note"] == "Add your registration number"


def test_only_admins_reach_the_admin_area(client):
    assert as_user(client, "bob").get("/api/v1/admin-panel/overview").status_code == 403
    assert client.get("/api/v1/admin-panel/me").json() == {"is_admin": False}
    owner = as_user(client, "owner")
    assert owner.get("/api/v1/admin-panel/me").json() == {"is_admin": True}
    stats = owner.get("/api/v1/admin-panel/overview").json()["data"]
    assert stats["users"]["total"] == 3
    assert stats["users"]["verified_email"] == 3
    assert len(stats["users"]["signups_14_days"]) == 14
    people = owner.get("/api/v1/admin-panel/users?q=bob").json()
    assert people["total"] == 1 and people["data"][0]["cash"] == 5000


def test_investing_takes_cash_and_raises_the_total(client):
    listing_id = listed_and_approved(client)
    bob = as_user(client, "bob")
    assert bob.post(f"/api/v1/opportunities/{listing_id}/invest", json={"amount": "500"}).status_code == 400  # under the minimum
    data = bob.post(f"/api/v1/opportunities/{listing_id}/invest", json={"amount": "1500"}).json()["data"]
    assert data["amount_raised"] == 1500
    assert data["my_investment"] == 1500
    assert data["investor_count"] == 1
    assert data["cash_available"] == 3500
    assert bob.post(f"/api/v1/opportunities/{listing_id}/invest", json={"amount": "4000"}).status_code == 400  # more than is left

    # The owner can't invest in their own business, nor delete it once people have
    alice = as_user(client, "alice")
    assert alice.post(f"/api/v1/opportunities/{listing_id}/invest", json={"amount": "1000"}).status_code == 403
    assert alice.delete(f"/api/v1/opportunities/{listing_id}").status_code == 409
    stats = as_user(client, "owner").get("/api/v1/admin-panel/overview").json()["data"]
    assert stats["investing"]["invested_in_listings"] == 1500


def test_not_enough_cash_is_refused(client):
    listing_id = listed_and_approved(client)
    as_user(client, "owner")
    response = client.post(f"/api/v1/opportunities/{listing_id}/invest", json={"amount": "1000"})
    assert response.status_code == 402


def test_rejects_minimum_above_goal_and_bad_category(client):
    assert client.post("/api/v1/opportunities", json=company(min_investment="600000")).status_code == 422
    assert client.post("/api/v1/opportunities", json=company(category="crypto")).status_code == 422
    assert client.post("/api/v1/opportunities", json=company(founded_year=3020)).status_code == 422
    assert client.get("/api/v1/opportunities").json()["total"] == 0


def test_only_the_owner_can_remove_a_listing(client):
    listing_id = listed_and_approved(client)
    assert as_user(client, "bob").delete(f"/api/v1/opportunities/{listing_id}").status_code == 403
    assert as_user(client, "alice").delete(f"/api/v1/opportunities/{listing_id}").status_code == 200
    assert client.get(f"/api/v1/opportunities/{listing_id}").status_code == 404
