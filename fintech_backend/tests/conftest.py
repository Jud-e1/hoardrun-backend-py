"""
Test configuration and fixtures.
"""

import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.config import Base, get_db
from app.database.models import User, Account, Transaction, Card
from app.config.settings import get_settings


# Test database URL - use SQLite for testing
TEST_DATABASE_URL = "sqlite:///./test_fintech.db"


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False  # Set to True for SQL debugging
    )
    return engine


@pytest.fixture(scope="session")
def test_session_factory(test_engine):
    """Create a test session factory."""
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def test_db(test_engine, test_session_factory):
    """Create a test database session."""
    # Create all tables
    Base.metadata.create_all(bind=test_engine)

    # Create a session
    session = test_session_factory()

    try:
        yield session
    finally:
        session.close()
        # Drop all tables after each test
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client(test_db):
    """Create a test client with database dependency override."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def test_app():
    """Return the FastAPI application instance for testing."""
    return app


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "phone_number": "+1234567890",
        "password_hash": "$2b$12$dummy_hash_for_testing",
        "country": "US",
        "status": "active",
        "role": "user"
    }


@pytest.fixture
def sample_account_data():
    """Sample account data for testing."""
    return {
        "account_number": "ACC1234567890",
        "account_name": "Test Account",
        "account_type": "CHECKING",
        "status": "ACTIVE",
        "current_balance": "1000.00",
        "available_balance": "1000.00",
        "pending_balance": "0.00",
        "reserved_balance": "0.00",
        "currency": "USD",
        "is_primary": True
    }


@pytest.fixture
def sample_transaction_data():
    """Sample transaction data for testing."""
    return {
        "transaction_type": "DEPOSIT",
        "status": "COMPLETED",
        "direction": "INBOUND",
        "amount": "100.00",
        "currency": "USD",
        "description": "Test transaction",
        "payment_method": "BANK_TRANSFER",
        "merchant_category": "OTHER"
    }