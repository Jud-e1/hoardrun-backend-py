"""
Unit tests for custom exceptions and exception handling.
"""
import pytest
from decimal import Decimal

from ...core.exceptions import (
    FintechException,
    ValidationException,
    InsufficientFundsException,
    CardFrozenException,
    CardNotFoundException,
    AccountNotFoundException,
    TransactionNotFoundException,
    TransferLimitExceededException,
    InvalidCurrencyException,
    ExternalServiceException,
    RateLimitExceededException,
    BusinessRuleViolationException
)


class TestFintechException:
    """Test cases for base FintechException."""
    
    def test_basic_exception_creation(self):
        """Test basic exception creation with required parameters."""
        exc = FintechException(
            message="Test error message",
            error_code="TEST_ERROR"
        )
        
        assert exc.message == "Test error message"
        assert exc.error_code == "TEST_ERROR"
        assert exc.status_code == 400  # default
        assert exc.details == {}  # default
        assert str(exc) == "Test error message"
    
    def test_exception_with_all_parameters(self):
        """Test exception creation with all parameters."""
        details = {"field": "test_field", "value": "test_value"}
        exc = FintechException(
            message="Custom error",
            error_code="CUSTOM_ERROR",
            status_code=422,
            details=details
        )
        
        assert exc.message == "Custom error"
        assert exc.error_code == "CUSTOM_ERROR"
        assert exc.status_code == 422
        assert exc.details == details
    
    def test_exception_inheritance(self):
        """Test that FintechException inherits from Exception."""
        exc = FintechException("Test", "TEST_ERROR")
        assert isinstance(exc, Exception)
        assert isinstance(exc, FintechException)


class TestValidationException:
    """Test cases for ValidationException."""
    
    def test_basic_validation_exception(self):
        """Test basic validation exception creation."""
        exc = ValidationException("Invalid input")
        
        assert exc.message == "Invalid input"
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.status_code == 422
        assert exc.details == {}
    
    def test_validation_exception_with_field(self):
        """Test validation exception with field information."""
        exc = ValidationException("Invalid email format", field="email")
        
        assert exc.message == "Invalid email format"
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.status_code == 422
        assert exc.details["field"] == "email"
    
    def test_validation_exception_with_field_and_value(self):
        """Test validation exception with field and value information."""
        exc = ValidationException(
            "Invalid email format", 
            field="email", 
            value="invalid-email"
        )
        
        assert exc.details["field"] == "email"
        assert exc.details["invalid_value"] == "invalid-email"


class TestInsufficientFundsException:
    """Test cases for InsufficientFundsException."""
    
    def test_insufficient_funds_exception(self):
        """Test insufficient funds exception creation."""
        exc = InsufficientFundsException(
            available_balance=Decimal("100.00"),
            requested_amount=Decimal("150.00")
        )
        
        assert "Insufficient funds" in exc.message
        assert "Available: 100.00 USD" in exc.message
        assert "Requested: 150.00 USD" in exc.message
        assert exc.error_code == "INSUFFICIENT_FUNDS"
        assert exc.status_code == 400
        
        assert exc.details["available_balance"] == "100.00"
        assert exc.details["requested_amount"] == "150.00"
        assert exc.details["currency"] == "USD"
        assert exc.details["shortfall"] == "50.00"
    
    def test_insufficient_funds_exception_custom_currency(self):
        """Test insufficient funds exception with custom currency."""
        exc = InsufficientFundsException(
            available_balance=Decimal("50.00"),
            requested_amount=Decimal("75.00"),
            currency="EUR"
        )
        
        assert "EUR" in exc.message
        assert exc.details["currency"] == "EUR"


class TestCardFrozenException:
    """Test cases for CardFrozenException."""
    
    def test_card_frozen_exception(self):
        """Test card frozen exception creation."""
        exc = CardFrozenException("card_123")
        
        assert "Card card_123 is frozen" in exc.message
        assert exc.error_code == "CARD_FROZEN"
        assert exc.status_code == 403
        assert exc.details["card_id"] == "card_123"


class TestCardNotFoundException:
    """Test cases for CardNotFoundException."""
    
    def test_card_not_found_exception(self):
        """Test card not found exception creation."""
        exc = CardNotFoundException("card_456")
        
        assert "Card with ID card_456 not found" in exc.message
        assert exc.error_code == "CARD_NOT_FOUND"
        assert exc.status_code == 404
        assert exc.details["card_id"] == "card_456"


class TestAccountNotFoundException:
    """Test cases for AccountNotFoundException."""
    
    def test_account_not_found_exception(self):
        """Test account not found exception creation."""
        exc = AccountNotFoundException("acc_789")
        
        assert "Account with ID acc_789 not found" in exc.message
        assert exc.error_code == "ACCOUNT_NOT_FOUND"
        assert exc.status_code == 404
        assert exc.details["account_id"] == "acc_789"


class TestTransactionNotFoundException:
    """Test cases for TransactionNotFoundException."""
    
    def test_transaction_not_found_exception(self):
        """Test transaction not found exception creation."""
        exc = TransactionNotFoundException("txn_101")
        
        assert "Transaction with ID txn_101 not found" in exc.message
        assert exc.error_code == "TRANSACTION_NOT_FOUND"
        assert exc.status_code == 404
        assert exc.details["transaction_id"] == "txn_101"


class TestTransferLimitExceededException:
    """Test cases for TransferLimitExceededException."""
    
    def test_transfer_limit_exceeded_exception(self):
        """Test transfer limit exceeded exception creation."""
        exc = TransferLimitExceededException(
            requested_amount=Decimal("5000.00"),
            daily_limit=Decimal("2000.00")
        )
        
        assert "Transfer amount 5000.00 USD exceeds daily limit of 2000.00 USD" in exc.message
        assert exc.error_code == "TRANSFER_LIMIT_EXCEEDED"
        assert exc.status_code == 400
        
        assert exc.details["requested_amount"] == "5000.00"
        assert exc.details["daily_limit"] == "2000.00"
        assert exc.details["currency"] == "USD"
    
    def test_transfer_limit_exceeded_exception_custom_currency(self):
        """Test transfer limit exceeded exception with custom currency."""
        exc = TransferLimitExceededException(
            requested_amount=Decimal("3000.00"),
            daily_limit=Decimal("1000.00"),
            currency="GBP"
        )
        
        assert "GBP" in exc.message
        assert exc.details["currency"] == "GBP"


class TestInvalidCurrencyException:
    """Test cases for InvalidCurrencyException."""
    
    def test_invalid_currency_exception(self):
        """Test invalid currency exception creation."""
        exc = InvalidCurrencyException("XYZ")
        
        assert "Currency 'XYZ' is not supported" in exc.message
        assert exc.error_code == "INVALID_CURRENCY"
        assert exc.status_code == 400
        assert exc.details["invalid_currency"] == "XYZ"
    
    def test_invalid_currency_exception_with_supported_list(self):
        """Test invalid currency exception with supported currencies list."""
        supported = ["USD", "EUR", "GBP"]
        exc = InvalidCurrencyException("XYZ", supported_currencies=supported)
        
        assert exc.details["invalid_currency"] == "XYZ"
        assert exc.details["supported_currencies"] == supported


class TestExternalServiceException:
    """Test cases for ExternalServiceException."""
    
    def test_external_service_exception(self):
        """Test external service exception creation."""
        exc = ExternalServiceException("PaymentGateway", "process_payment")
        
        assert "External service 'PaymentGateway' failed during 'process_payment'" in exc.message
        assert exc.error_code == "EXTERNAL_SERVICE_ERROR"
        assert exc.status_code == 502
        
        assert exc.details["service_name"] == "PaymentGateway"
        assert exc.details["operation"] == "process_payment"
    
    def test_external_service_exception_with_error_message(self):
        """Test external service exception with error message."""
        exc = ExternalServiceException(
            "BankAPI", 
            "get_balance", 
            error_message="Connection timeout"
        )
        
        assert "Connection timeout" in exc.message
        assert exc.details["service_error"] == "Connection timeout"


class TestRateLimitExceededException:
    """Test cases for RateLimitExceededException."""
    
    def test_rate_limit_exceeded_exception(self):
        """Test rate limit exceeded exception creation."""
        exc = RateLimitExceededException(limit=100, window_seconds=60)
        
        assert "Rate limit exceeded: 100 requests per 60 seconds" in exc.message
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"
        assert exc.status_code == 429
        
        assert exc.details["limit"] == 100
        assert exc.details["window_seconds"] == 60
    
    def test_rate_limit_exceeded_exception_with_retry_after(self):
        """Test rate limit exceeded exception with retry after."""
        exc = RateLimitExceededException(
            limit=50, 
            window_seconds=60, 
            retry_after=30
        )
        
        assert exc.details["retry_after_seconds"] == 30


class TestBusinessRuleViolationException:
    """Test cases for BusinessRuleViolationException."""
    
    def test_business_rule_violation_exception(self):
        """Test business rule violation exception creation."""
        exc = BusinessRuleViolationException(
            "MinimumBalance", 
            "Account balance cannot go below $10"
        )
        
        assert "Business rule violation: MinimumBalance" in exc.message
        assert "Account balance cannot go below $10" in exc.message
        assert exc.error_code == "BUSINESS_RULE_VIOLATION"
        assert exc.status_code == 400
        
        assert exc.details["rule_name"] == "MinimumBalance"
        assert exc.details["violation_details"] == "Account balance cannot go below $10"


class TestExceptionInheritance:
    """Test cases for exception inheritance and polymorphism."""
    
    def test_all_exceptions_inherit_from_fintech_exception(self):
        """Test that all custom exceptions inherit from FintechException."""
        exception_classes = [
            ValidationException,
            InsufficientFundsException,
            CardFrozenException,
            CardNotFoundException,
            AccountNotFoundException,
            TransactionNotFoundException,
            TransferLimitExceededException,
            InvalidCurrencyException,
            ExternalServiceException,
            RateLimitExceededException,
            BusinessRuleViolationException
        ]
        
        for exc_class in exception_classes:
            assert issubclass(exc_class, FintechException)
            assert issubclass(exc_class, Exception)
    
    def test_exception_polymorphism(self):
        """Test that exceptions can be caught as FintechException."""
        exceptions = [
            ValidationException("Test"),
            InsufficientFundsException(Decimal("10"), Decimal("20")),
            CardFrozenException("card_123"),
            ExternalServiceException("TestService", "test_operation")
        ]
        
        for exc in exceptions:
            # Should be catchable as FintechException
            assert isinstance(exc, FintechException)
            # Should have required attributes
            assert hasattr(exc, 'message')
            assert hasattr(exc, 'error_code')
            assert hasattr(exc, 'status_code')
            assert hasattr(exc, 'details')


class TestExceptionDetails:
    """Test cases for exception details and metadata."""
    
    def test_exception_details_are_serializable(self):
        """Test that exception details can be serialized to JSON."""
        import json
        
        exc = InsufficientFundsException(
            available_balance=Decimal("100.50"),
            requested_amount=Decimal("200.75"),
            currency="USD"
        )
        
        # Details should be JSON serializable
        details_json = json.dumps(exc.details)
        assert isinstance(details_json, str)
        
        # Should be able to deserialize back
        details_dict = json.loads(details_json)
        assert details_dict["available_balance"] == "100.50"
        assert details_dict["requested_amount"] == "200.75"
        assert details_dict["currency"] == "USD"
    
    def test_exception_message_formatting(self):
        """Test that exception messages are properly formatted."""
        exc = InsufficientFundsException(
            available_balance=Decimal("0.00"),
            requested_amount=Decimal("50.00"),
            currency="EUR"
        )
        
        message = exc.message
        assert "Insufficient funds" in message
        assert "0.00 EUR" in message
        assert "50.00 EUR" in message
        
        # Message should be suitable for user display
        assert len(message) > 0
        assert message[0].isupper()  # Should start with capital letter