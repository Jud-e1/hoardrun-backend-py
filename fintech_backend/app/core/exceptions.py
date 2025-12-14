"""
Custom exception hierarchy for fintech operations.
"""
from decimal import Decimal
from typing import Optional, Dict, Any


class FintechException(Exception):
    """Base exception for fintech operations."""
    
    def __init__(
        self, 
        message: str, 
        error_code: str, 
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationException(FintechException):
    """Exception for data validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["invalid_value"] = str(value)
            
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            details=details
        )


class InsufficientFundsException(FintechException):
    """Exception for insufficient funds scenarios."""
    
    def __init__(self, available_balance: Decimal, requested_amount: Decimal, currency: str = "USD"):
        message = f"Insufficient funds. Available: {available_balance} {currency}, Requested: {requested_amount} {currency}"
        details = {
            "available_balance": str(available_balance),
            "requested_amount": str(requested_amount),
            "currency": currency,
            "shortfall": str(requested_amount - available_balance)
        }
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_FUNDS",
            status_code=400,
            details=details
        )


class CardFrozenException(FintechException):
    """Exception for operations on frozen cards."""
    
    def __init__(self, card_id: str):
        message = f"Card {card_id} is frozen and cannot be used for transactions"
        details = {"card_id": card_id}
        super().__init__(
            message=message,
            error_code="CARD_FROZEN",
            status_code=403,
            details=details
        )


class CardNotFoundException(FintechException):
    """Exception for card not found scenarios."""
    
    def __init__(self, card_id: str):
        message = f"Card with ID {card_id} not found"
        details = {"card_id": card_id}
        super().__init__(
            message=message,
            error_code="CARD_NOT_FOUND",
            status_code=404,
            details=details
        )


class AccountNotFoundException(FintechException):
    """Exception for account not found scenarios."""
    
    def __init__(self, account_id: str):
        message = f"Account with ID {account_id} not found"
        details = {"account_id": account_id}
        super().__init__(
            message=message,
            error_code="ACCOUNT_NOT_FOUND",
            status_code=404,
            details=details
        )


class TransactionNotFoundException(FintechException):
    """Exception for transaction not found scenarios."""
    
    def __init__(self, transaction_id: str):
        message = f"Transaction with ID {transaction_id} not found"
        details = {"transaction_id": transaction_id}
        super().__init__(
            message=message,
            error_code="TRANSACTION_NOT_FOUND",
            status_code=404,
            details=details
        )


class TransferLimitExceededException(FintechException):
    """Exception for transfer limit violations."""
    
    def __init__(self, requested_amount: Decimal, daily_limit: Decimal, currency: str = "USD"):
        message = f"Transfer amount {requested_amount} {currency} exceeds daily limit of {daily_limit} {currency}"
        details = {
            "requested_amount": str(requested_amount),
            "daily_limit": str(daily_limit),
            "currency": currency
        }
        super().__init__(
            message=message,
            error_code="TRANSFER_LIMIT_EXCEEDED",
            status_code=400,
            details=details
        )


class InvalidCurrencyException(FintechException):
    """Exception for invalid currency operations."""
    
    def __init__(self, currency: str, supported_currencies: Optional[list] = None):
        message = f"Currency '{currency}' is not supported"
        details = {"invalid_currency": currency}
        if supported_currencies:
            details["supported_currencies"] = supported_currencies
            
        super().__init__(
            message=message,
            error_code="INVALID_CURRENCY",
            status_code=400,
            details=details
        )


class ExternalServiceException(FintechException):
    """Exception for external service failures."""
    
    def __init__(self, service_name: str, operation: str, error_message: Optional[str] = None):
        message = f"External service '{service_name}' failed during '{operation}'"
        if error_message:
            message += f": {error_message}"
            
        details = {
            "service_name": service_name,
            "operation": operation
        }
        if error_message:
            details["service_error"] = error_message
            
        super().__init__(
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details=details
        )


class RateLimitExceededException(FintechException):
    """Exception for rate limit violations."""
    
    def __init__(self, limit: int, window_seconds: int, retry_after: Optional[int] = None):
        message = f"Rate limit exceeded: {limit} requests per {window_seconds} seconds"
        details = {
            "limit": limit,
            "window_seconds": window_seconds
        }
        if retry_after:
            details["retry_after_seconds"] = retry_after
            
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details
        )


class BusinessRuleViolationException(FintechException):
    """Exception for business rule violations."""
    
    def __init__(self, rule_name: str, violation_details: str):
        message = f"Business rule violation: {rule_name} - {violation_details}"
        details = {
            "rule_name": rule_name,
            "violation_details": violation_details
        }
        super().__init__(
            message=message,
            error_code="BUSINESS_RULE_VIOLATION",
            status_code=400,
            details=details
        )


class AuthenticationException(FintechException):
    """Exception for authentication failures."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_FAILED",
            status_code=401
        )


class AuthorizationException(FintechException):
    """Exception for authorization failures."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            error_code="ACCESS_DENIED",
            status_code=403
        )


class UserNotFoundException(FintechException):
    """Exception for user not found scenarios."""
    
    def __init__(self, user_identifier: str):
        message = f"User not found: {user_identifier}"
        details = {"user_identifier": user_identifier}
        super().__init__(
            message=message,
            error_code="USER_NOT_FOUND",
            status_code=404,
            details=details
        )


class EmailAlreadyExistsException(FintechException):
    """Exception for duplicate email registration."""
    
    def __init__(self, email: str):
        message = f"Email address {email} is already registered"
        details = {"email": email}
        super().__init__(
            message=message,
            error_code="EMAIL_ALREADY_EXISTS",
            status_code=409,
            details=details
        )


class TokenExpiredException(FintechException):
    """Exception for expired tokens."""
    
    def __init__(self, token_type: str = "token"):
        message = f"The {token_type} has expired"
        details = {"token_type": token_type}
        super().__init__(
            message=message,
            error_code="TOKEN_EXPIRED",
            status_code=401,
            details=details
        )


class InvalidTokenException(FintechException):
    """Exception for invalid tokens."""
    
    def __init__(self, token_type: str = "token"):
        message = f"The {token_type} is invalid"
        details = {"token_type": token_type}
        super().__init__(
            message=message,
            error_code="INVALID_TOKEN",
            status_code=401,
            details=details
        )


# Aliases for common exception names
NotFoundError = TransactionNotFoundException
ValidationError = ValidationException
BusinessLogicError = BusinessRuleViolationException
ConflictError = EmailAlreadyExistsException
AuthenticationError = AuthenticationException
UnauthorizedError = AuthorizationException
InsufficientFundsError = InsufficientFundsException 
ServiceError = FintechException
