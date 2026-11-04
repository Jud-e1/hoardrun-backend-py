"""
Company listings behind the investment opportunities page.

Run from fintech_backend with:
PYTHONPATH=. python -m pytest tests/unit/test_company_listings.py --noconftest --import-mode=importlib
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

from app.api.v1 import opportunities
from app.auth.dependencies import get_current_user_id
from app.database import listing_models  # noqa: F401 - registers the table
from app.database.config import Base, get_db
from app.database.models import User


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        for user_id in ("alice", "bob"):
            db.add(User(id=user_id, email=f"{user_id}@example.com", password_hash="x", first_name=user_id, last_name="Test"))
        db.commit()

    app = FastAPI()
    app.include_router(opportunities.router, prefix="/api/v1")
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
        "funding_goal": "500000",
        "min_investment": "1000",
        "target_return": "15-20%",
        "risk_level": "high",
    }
    body.update(overrides)
    return body


def test_empty_until_a_company_is_listed(client):
    response = client.get("/api/v1/opportunities?category=private-equity")
    assert response.status_code == 200
    assert response.json() == {"data": [], "total": 0}


def test_listed_company_is_stored_and_shown_in_its_category_only(client):
    created = client.post("/api/v1/opportunities", json=company())
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["name"] == "Northwind Labs"
    assert data["website"] == "https://northwind.example"
    assert data["amount_raised"] == 0
    assert data["is_owner"] is True

    assert client.get("/api/v1/opportunities?category=private-equity").json()["total"] == 1
    assert client.get("/api/v1/opportunities?category=real-estate").json()["total"] == 0
    assert client.get("/api/v1/opportunities?q=delivery").json()["total"] == 1
    assert client.get("/api/v1/opportunities?q=bakery").json()["total"] == 0

    client.current["user"] = "bob"
    seen_by_bob = client.get(f"/api/v1/opportunities/{data['id']}").json()["data"]
    assert seen_by_bob["is_owner"] is False


def test_rejects_minimum_above_goal_and_bad_category(client):
    assert client.post("/api/v1/opportunities", json=company(min_investment="600000")).status_code == 422
    assert client.post("/api/v1/opportunities", json=company(category="crypto")).status_code == 422
    assert client.post("/api/v1/opportunities", json=company(founded_year=3020)).status_code == 422
    assert client.get("/api/v1/opportunities").json()["total"] == 0


def test_only_the_owner_can_remove_a_listing(client):
    listing_id = client.post("/api/v1/opportunities", json=company()).json()["data"]["id"]

    client.current["user"] = "bob"
    assert client.delete(f"/api/v1/opportunities/{listing_id}").status_code == 403

    client.current["user"] = "alice"
    assert client.delete(f"/api/v1/opportunities/{listing_id}").status_code == 200
    assert client.get(f"/api/v1/opportunities/{listing_id}").status_code == 404
