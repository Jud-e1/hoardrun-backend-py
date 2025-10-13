"""
Integration tests for database functionality.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from app.database.models import (
    User, Account, Transaction, Card, Investment, P2PTransaction, Transfer,
    AccountTypeEnum, AccountStatusEnum, TransactionTypeEnum, 
    TransactionStatusEnum, TransactionDirectionEnum, MerchantCategoryEnum,
    PaymentMethodEnum, CardTypeEnum, CardStatusEnum
)
from app.database.config import check_database_connection, get_database_info


class TestDatabaseConnection:
    """Test database connection and basic functionality."""
    
    def test_database_connection(self, test_db):
        """Test that database connection works."""
        # Execute a simple query
        result = test_db.execute(text("SELECT 1 as test"))
        assert result.fetchone()[0] == 1
    
    def test_database_info_function(self):
        """Test database info function."""
        db_info = get_database_info()
        assert isinstance(db_info, dict)
        assert "database_url" in db_info
        assert "connection_healthy" in db_info
    
    def test_check_database_connection_function(self):
        """Test database connection check function."""
        result = check_database_connection()
        assert isinstance(result, bool)


class TestUserModel:
    """Test User model functionality."""
    
    def test_create_user(self, test_db, sample_user_data):
        """Test creating a user."""
        user = User(**sample_user_data)
        test_db.add(user)
        test_db.commit()
        
        # Verify user was created
        saved_user = test_db.query(User).filter(User.email == sample_user_data["email"]).first()
        assert saved_user is not None
        assert saved_user.email == sample_user_data["email"]
        assert saved_user.first_name == sample_user_data["first_name"]
        assert saved_user.full_name == f"{sample_user_data['first_name']} {sample_user_data['last_name']}"
    
    def test_user_email_validation(self, test_db):
        """Test user email validation."""
        # Valid email
        user = User(
            email="valid@example.com",
            first_name="Test",
            last_name="User",
            password_hash="hash"
        )
        test_db.add(user)
        test_db.commit()
        assert user.email == "valid@example.com"
        
        # Invalid email should raise ValueError
        with pytest.raises(ValueError, match="Invalid email format"):
            User(
                email="invalid-email",
                first_name="Test",
                last_name="User",
                password_hash="hash"
            )
    
    def test_user_phone_validation(self, test_db):
        """Test user phone number validation."""
        # Valid phone number
        user = User(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            phone_number="+1234567890",
            password_hash="hash"
        )
        test_db.add(user)
        test_db.commit()
        assert user.phone_number == "+1234567890"
        
        # Invalid phone number should raise ValueError
        with pytest.raises(ValueError, match="Invalid phone number format"):
            User(
                email="test2@example.com",
                first_name="Test",
                last_name="User",
                phone_number="invalid-phone",
                password_hash="hash"
            )
    
    def test_user_unique_email_constraint(self, test_db, sample_user_data):
        """Test that email must be unique."""
        # Create first user
        user1 = User(**sample_user_data)
        test_db.add(user1)
        test_db.commit()
        
        # Try to create second user with same email
        user2_data = sample_user_data.copy()
        user2_data["first_name"] = "Another"
        user2 = User(**user2_data)
        test_db.add(user2)
        
        with pytest.raises(IntegrityError):
            test_db.commit()


class TestAccountModel:
    """Test Account model functionality."""
    
    def test_create_account(self, test_db, sample_user_data, sample_account_data):
        """Test creating an account."""
        # Create user first
        user = User(**sample_user_data)
        test_db.add(user)
        test_db.flush()
        
        # Create account
        account_data = sample_account_data.copy()
        account_data["user_id"] = user.id
        account = Account(**account_data)
        test_db.add(account)
        test_db.commit()
        
        # Verify account was created
        saved_account = test_db.query(Account).filter(
            Account.account_number == account_data["account_number"]
        ).first()
        assert saved_account is not None
        assert saved_account.user_id == user.id
        assert saved_account.account_type == AccountTypeEnum.CHECKING
        assert saved_account.effective_balance == Decimal("1000.00")
    
    def test_account_number_validation(self, test_db, sample_user_data):
        """Test account number validation."""
        user = User(**sample_user_data)
        test_db.add(user)
        test_db.flush()
        
        # Valid account number
        account = Account(
            user_id=user.id,
            account_number="ACC1234567890",
            account_name="Test Account",
            account_type=AccountTypeEnum.CHECKING,
            currency="USD"
        )
        test_db.add(account)
        test_db.commit()
        
        # Invalid account number should raise ValueError
        with pytest.raises(ValueError, match="Account number must be 10-20 alphanumeric characters"):
            Account(
                user_id=user.id,
                account_number="invalid",
                account_name="Test Account",
                account_type=AccountTypeEnum.CHECKING,
                currency="USD"
            )
    
    def test_account_currency_validation(self, test_db, sample_user_data):
        """Test account currency validation."""
        user = User(**sample_user_data)
        test_db.add(user)
        test_db.flush()
        
        # Valid currency
        account = Account(
            user_id=user.id,
            account_number="ACC1234567890",
            account_name="Test Account",
            account_type=AccountTypeEnum.CHECKING,
            currency="USD"
        )
        test_db.add(account)
        test_db.commit()
        assert account.currency == "USD"
        
        # Invalid currency should raise ValueError
        with pytest.raises(ValueError, match="Currency must be a 3-letter ISO code"):
            Account(
                user_id=user.id,
                account_number="ACC1234567891",
                account_name="Test Account",
                account_type=AccountTypeEnum.CHECKING,
                currency="INVALID"
            )


class TestTransactionModel:
    """Test Transaction model functionality."""
    
    def test_create_transaction(self, test_db, sample_user_data, sample_account_data, sample_transaction_data):
        """Test creating a transaction."""
        # Create user and account first
        user = User(**sample_user_data)
        test_db.add(user)
        test_db.flush()
        
        account_data = sample_account_data.copy()
        account_data["user_id"] = user.id
        account = Account(**account_data)
        test_db.add(account)
        test_db.flush()
        
        # Create transaction
        transaction_data = sample_transaction_data.copy()
        transaction_data["user_id"] = user.id
        transaction_data["account_id"] = account.id
        transaction_data["transaction_date"] = datetime.now(timezone.utc)
        
        transaction = Transaction(**transaction_data)
        test_db.add(transaction)
        test_db.commit()
        
        # Verify transaction was created
        saved_transaction = test_db.query(Transaction).filter(
            Transaction.user_id == user.id
        ).first()
        assert saved_transaction is not None
        assert saved_transaction.amount == Decimal("100.00")
        assert saved_transaction.total_amount == Decimal("100.00")  # amount + fee_amount
    
    def test_transaction_currency_validation(self, test_db, sample_user_data, sample_account_data):
        """Test transaction currency validation."""
        # Create user and account first
        user = User(**sample_user_data)
        test_db.add(user)
        test_db.flush()
        
        account_data = sample_account_data.copy()
        account_data["user_id"] = user.id
        account = Account(**account_data)
        test_db.add(account)
        test_db.flush()
        
        # Valid currency
        transaction = Transaction(
            user_id=user.id,
            account_id=account.id,
            transaction_type=TransactionTypeEnum.DEPOSIT,
            status=TransactionStatusEnum.COMPLETED,
            direction=TransactionDirectionEnum.INBOUND,
            amount=Decimal("100.00"),
            currency="USD",
            description="Test transaction",
            payment_method=PaymentMethodEnum.BANK_TRANSFER,
            transaction_date=datetime.now(timezone.utc)
        )
        test_db.add(transaction)
        test_db.commit()
        assert transaction.currency == "USD"
        
        # Invalid currency should raise ValueError
        with pytest.raises(ValueError, match="currency must be a 3-letter ISO code"):
            Transaction(
                user_id=user.id,
                account_id=account.id,
                transaction_type=TransactionTypeEnum.DEPOSIT,
                status=TransactionStatusEnum.COMPLETED,
                direction=TransactionDirectionEnum.INBOUND,
                amount=Decimal("100.00"),
                currency="INVALID",
                description="Test transaction",
                payment_method=PaymentMethodEnum.BANK_TRANSFER,
                transaction_date=datetime.now(timezone.utc)
            )


class TestCardModel:
    """Test Card model functionality."""
    
    def test_create_card(self, test_db, sample_user_data, sample_account_data):
        """Test creating a card."""
        # Create user and account first
        user = User(**sample_user_data)
        test_db.add(user)
        test_db.flush()
        
        account_data = sample_account_data.copy()
        account_data["user_id"] = user.id
        account = Account(**account_data)
        test_db.add(account)
        test_db.flush()
        
        # Create card
        card = Card(
            user_id=user.id,
            account_id=account.id,
            card_number_masked="****1234",
            card_type=CardTypeEnum.DEBIT,
            cardholder_name="TEST USER",
            expiry_month=12,
            expiry_year=2025
        )
        test_db.add(card)
        test_db.commit()
        
        # Verify card was created
        saved_card = test_db.query(Card).filter(Card.user_id == user.id).first()
        assert saved_card is not None
        assert saved_card.card_number_masked == "****1234"
        assert saved_card.cardholder_name == "TEST USER"
        assert not saved_card.is_expired
        assert not saved_card.is_blocked
    
    def test_card_validation(self, test_db, sample_user_data, sample_account_data):
        """Test card validation."""
        # Create user and account first
        user = User(**sample_user_data)
        test_db.add(user)
        test_db.flush()
        
        account_data = sample_account_data.copy()
        account_data["user_id"] = user.id
        account = Account(**account_data)
        test_db.add(account)
        test_db.flush()
        
        # Invalid card number format should raise ValueError
        with pytest.raises(ValueError, match="Card number must be masked"):
            Card(
                user_id=user.id,
                account_id=account.id,
                card_number_masked="1234567890123456",  # Not masked
                card_type=CardTypeEnum.DEBIT,
                cardholder_name="TEST USER",
                expiry_month=12,
                expiry_year=2025
            )


class TestModelRelationships:
    """Test model relationships and cascading."""
    
    def test_user_account_relationship(self, test_db, sample_user_data, sample_account_data):
        """Test user-account relationship."""
        # Create user
        user = User(**sample_user_data)
        test_db.add(user)
        test_db.flush()
        
        # Create account
        account_data = sample_account_data.copy()
        account_data["user_id"] = user.id
        account = Account(**account_data)
        test_db.add(account)
        test_db.commit()
        
        # Test relationship
        assert len(user.accounts) == 1
        assert user.accounts[0].id == account.id
        assert account.user.id == user.id
    
    def test_cascade_delete(self, test_db, sample_user_data, sample_account_data):
        """Test cascade delete functionality."""
        # Create user and account
        user = User(**sample_user_data)
        test_db.add(user)
        test_db.flush()
        
        account_data = sample_account_data.copy()
        account_data["user_id"] = user.id
        account = Account(**account_data)
        test_db.add(account)
        test_db.commit()
        
        # Delete user should cascade to accounts
        test_db.delete(user)
        test_db.commit()
        
        # Verify account was also deleted
        remaining_accounts = test_db.query(Account).filter(Account.user_id == user.id).all()
        assert len(remaining_accounts) == 0
