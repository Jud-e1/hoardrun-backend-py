"""
Unit tests for Plaid service functionality.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal

from fintech_backend.app.services.plaid_service import PlaidService
from fintech_backend.app.services.account_service import AccountService
from fintech_backend.app.models.plaid import PlaidAccount, PlaidConnection
from fintech_backend.app.models.account import Account
from fintech_backend.app.core.exceptions import ServiceError


class TestPlaidService:
    """Test cases for PlaidService."""

    @pytest.fixture
    def mock_repository(self):
        """Mock repository for testing."""
        return Mock()

    @pytest.fixture
    def mock_account_service(self):
        """Mock account service for testing."""
        return Mock()

    @pytest.fixture
    def plaid_service(self, mock_repository, mock_account_service):
        """Create PlaidService instance with mocked dependencies."""
        with patch('fintech_backend.app.services.plaid_service.get_repository_manager') as mock_get_repo, \
             patch('fintech_backend.app.services.plaid_service.get_plaid_client') as mock_get_plaid, \
             patch('fintech_backend.app.services.plaid_service.get_account_service') as mock_get_account:
            
            # Configure the mocks to return our fixtures
            mock_get_repo.return_value = mock_repository
            mock_get_plaid.return_value = Mock()
            mock_get_account.return_value = mock_account_service
            
            # Now create the service - it will use our mocked dependencies
            service = PlaidService()
            return service

    @pytest.fixture
    def sample_plaid_account_data(self):
        """Sample Plaid account data for testing."""
        return {
            "account_id": "acc_1234567890",
            "name": "Checking Account",
            "official_name": "Premium Checking",
            "type": "depository",
            "subtype": "checking",
            "mask": "1234",
            "balances": {
                "available": 1500.50,
                "current": 1500.50,
                "iso_currency_code": "USD"
            }
        }

    @pytest.fixture
    def sample_plaid_connection(self):
        """Sample Plaid connection for testing."""
        return PlaidConnection(
            connection_id="conn_123",
            user_id="user_123",
            access_token="access_token_123",
            item_id="item_123",
            institution_id="ins_123",
            institution_name="Test Bank"
        )

    @pytest.mark.asyncio
    async def test_create_internal_account_for_plaid_account_depository_checking(self, plaid_service, mock_account_service, sample_plaid_account_data):
        """Test creating internal account for depository checking account."""
        # Mock account service to return empty list (no existing account)
        mock_account_service.list_user_accounts = AsyncMock(return_value={"accounts": []})

        # Mock account creation
        mock_created_account = Mock()
        mock_created_account.account_id = "acc_internal_123"
        mock_created_account.account_name = "Checking Account"
        mock_created_account.account_type = "CHECKING"
        mock_created_account.plaid_account_id = "acc_1234567890"
        mock_account_service.create_account = AsyncMock(return_value=mock_created_account)

        # Call the method
        await plaid_service._create_internal_account_for_plaid_account(
            "user_123", sample_plaid_account_data
        )

        # Assertions
        mock_account_service.list_user_accounts.assert_called_once_with("user_123")
        mock_account_service.create_account.assert_called_once()

        # Check the account creation call arguments
        call_args = mock_account_service.create_account.call_args[0]
        user_id = call_args[0]
        account_request = call_args[1]
        
        assert user_id == "user_123"
        assert account_request.account_name == "Checking Account"
        assert account_request.account_type.value == "checking"
        assert account_request.currency.value == "USD"
        assert account_request.plaid_account_id == "acc_1234567890"

    @pytest.mark.asyncio
    async def test_create_internal_account_for_plaid_account_depository_savings(self, plaid_service, mock_account_service):
        """Test creating internal account for depository savings account."""
        account_data = {
            "account_id": "acc_savings_123",
            "name": "Savings Account",
            "type": "depository",
            "subtype": "savings",
            "balances": {
                "available": 5000.00,
                "current": 5000.00,
                "iso_currency_code": "USD"
            }
        }

        mock_account_service.list_user_accounts = AsyncMock(return_value={"accounts": []})
        mock_created_account = Mock()
        mock_created_account.account_type = "SAVINGS"
        mock_account_service.create_account = AsyncMock(return_value=mock_created_account)

        await plaid_service._create_internal_account_for_plaid_account(
            "user_123", account_data
        )

        call_args = mock_account_service.create_account.call_args[0]
        account_request = call_args[1]
        assert account_request.account_type.value == "savings"

    @pytest.mark.asyncio
    async def test_create_internal_account_for_plaid_account_credit_card(self, plaid_service, mock_account_service):
        """Test creating internal account for credit card account."""
        account_data = {
            "account_id": "acc_credit_123",
            "name": "Credit Card",
            "type": "credit",
            "subtype": "credit card",
            "balances": {
                "available": 2000.00,
                "current": -500.00,
                "iso_currency_code": "USD"
            }
        }

        mock_account_service.list_user_accounts = AsyncMock(return_value={"accounts": []})
        mock_created_account = Mock()
        mock_created_account.account_type = "CREDIT"
        mock_account_service.create_account = AsyncMock(return_value=mock_created_account)

        await plaid_service._create_internal_account_for_plaid_account(
            "user_123", account_data
        )

        call_args = mock_account_service.create_account.call_args[0]
        account_request = call_args[1]
        assert account_request.account_type.value == "credit"

    @pytest.mark.asyncio
    async def test_create_internal_account_for_plaid_account_investment(self, plaid_service, mock_account_service):
        """Test creating internal account for investment account."""
        account_data = {
            "account_id": "acc_investment_123",
            "name": "Investment Account",
            "type": "investment",
            "subtype": "brokerage",
            "balances": {
                "available": None,
                "current": 10000.00,
                "iso_currency_code": "USD"
            }
        }

        mock_account_service.list_user_accounts = AsyncMock(return_value={"accounts": []})
        mock_created_account = Mock()
        mock_created_account.account_type = "INVESTMENT"
        mock_account_service.create_account = AsyncMock(return_value=mock_created_account)

        await plaid_service._create_internal_account_for_plaid_account(
            "user_123", account_data
        )

        call_args = mock_account_service.create_account.call_args[0]
        account_request = call_args[1]
        assert account_request.account_type.value == "investment"

    @pytest.mark.asyncio
    async def test_create_internal_account_duplicate_prevention(self, plaid_service, mock_account_service, sample_plaid_account_data):
        """Test that duplicate internal accounts are not created."""
        # Mock existing account
        existing_account = Mock()
        existing_account.plaid_account_id = "acc_1234567890"
        mock_account_service.list_user_accounts = AsyncMock(return_value={"accounts": [existing_account]})

        # Call the method
        await plaid_service._create_internal_account_for_plaid_account(
            "user_123", sample_plaid_account_data
        )

        # Assertions
        mock_account_service.list_user_accounts.assert_called_once_with("user_123")
        # create_account should not be called since account already exists
        mock_account_service.create_account.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_internal_account_error_handling(self, plaid_service, mock_account_service, sample_plaid_account_data):
        """Test error handling during account creation."""
        mock_account_service.list_user_accounts = AsyncMock(return_value={"accounts": []})
        mock_account_service.create_account = AsyncMock(side_effect=ServiceError("Account creation failed"))

        # Call the method - should not raise exception (errors are logged but not raised)
        await plaid_service._create_internal_account_for_plaid_account(
            "user_123", sample_plaid_account_data
        )

        # Should have attempted to create account
        mock_account_service.create_account.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_internal_account_balance_handling(self, plaid_service, mock_account_service):
        """Test balance handling for different scenarios."""
        account_data = {
            "account_id": "acc_balance_test",
            "name": "Balance Test Account",
            "type": "depository",
            "subtype": "checking",
            "balances": {
                "available": 1000.00,
                "current": 1200.00,
                "iso_currency_code": "USD"
            }
        }

        mock_account_service.list_user_accounts = AsyncMock(return_value={"accounts": []})
        mock_created_account = Mock()
        mock_account_service.create_account = AsyncMock(return_value=mock_created_account)

        await plaid_service._create_internal_account_for_plaid_account(
            "user_123", account_data
        )

        # Verify create_account was called
        mock_account_service.create_account.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_internal_account_null_balances(self, plaid_service, mock_account_service):
        """Test handling of null balances."""
        account_data = {
            "account_id": "acc_null_balance",
            "name": "Null Balance Account",
            "type": "depository",
            "subtype": "checking",
            "balances": {
                "available": None,
                "current": None,
                "iso_currency_code": "USD"
            }
        }

        mock_account_service.list_user_accounts = AsyncMock(return_value={"accounts": []})
        mock_created_account = Mock()
        mock_account_service.create_account = AsyncMock(return_value=mock_created_account)

        await plaid_service._create_internal_account_for_plaid_account(
            "user_123", account_data
        )

        # Verify create_account was called
        mock_account_service.create_account.assert_called_once()

        