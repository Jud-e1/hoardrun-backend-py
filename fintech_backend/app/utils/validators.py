"""
Custom validators for financial data validation.
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
from datetime import datetime, date

from pydantic import field_validator, ValidationError
from ..core.exceptions import ValidationException


class FinancialValidators:
    """Collection of financial data validators."""
    
    @staticmethod
    def validate_amount(amount: Any, min_amount: Optional[Decimal] = None, max_amount: Optional[Decimal] = None) -> Decimal:
        """Validate monetary amount."""
        try:
            if isinstance(amount, str):
                # Remove currency symbols and formatting
                cleaned_amount = re.sub(r'[^\d.-]', '', amount)
                decimal_amount = Decimal(cleaned_amount)
            elif isinstance(amount, (int, float)):
                decimal_amount = Decimal(str(amount))
            elif isinstance(amount, Decimal):
                decimal_amount = amount
            else:
                raise ValidationException(f"Invalid amount format: {amount}")
            
            # Check for negative amounts
            if decimal_amount < 0:
                raise ValidationException("Amount cannot be negative")
            
            # Check minimum amount
            if min_amount is not None and decimal_amount < min_amount:
                raise ValidationException(f"Amount {decimal_amount} is below minimum {min_amount}")
            
            # Check maximum amount
            if max_amount is not None and decimal_amount > max_amount:
                raise ValidationException(f"Amount {decimal_amount} exceeds maximum {max_amount}")
            
            # Validate decimal places (max 2 for currency)
            if decimal_amount.as_tuple().exponent < -2:
                raise ValidationException("Amount cannot have more than 2 decimal places")
            
            return decimal_amount
            
        except (InvalidOperation, ValueError) as e:
            raise ValidationException(f"Invalid amount format: {amount}")
    
    @staticmethod
    def validate_currency_code(currency: str, supported_currencies: List[str]) -> str:
        """Validate currency code format and support."""
        if not isinstance(currency, str):
            raise ValidationException("Currency code must be a string")
        
        currency = currency.upper().strip()
        
        # Check format (3 letter alphabetic code)
        if not re.match(r'^[A-Z]{3}$', currency):
            raise ValidationException("Currency code must be a 3-letter alphabetic code")
        
        # Check if supported
        if currency not in supported_currencies:
            raise ValidationException(f"Currency {currency} is not supported. Supported currencies: {supported_currencies}")
        
        return currency
    
    @staticmethod
    def validate_account_number(account_number: str) -> str:
        """Validate account number format."""
        if not isinstance(account_number, str):
            raise ValidationException("Account number must be a string")
        
        account_number = account_number.strip()
        
        # Check length (typically 8-17 digits)
        if len(account_number) < 8 or len(account_number) > 17:
            raise ValidationException("Account number must be 8-17 characters long")
        
        # Check format (alphanumeric)
        if not re.match(r'^[A-Z0-9]+$', account_number.upper()):
            raise ValidationException("Account number must contain only letters and numbers")
        
        return account_number.upper()
    
    @staticmethod
    def validate_card_number(card_number: str, allow_masked: bool = True) -> str:
        """Validate card number format."""
        if not isinstance(card_number, str):
            raise ValidationException("Card number must be a string")
        
        card_number = card_number.strip()
        
        # Remove spaces and dashes
        cleaned_number = re.sub(r'[\s-]', '', card_number)
        
        if allow_masked and '*' in cleaned_number:
            # Validate masked format (e.g., ****-****-****-1234)
            if not re.match(r'^[\*\d-]+$', card_number):
                raise ValidationException("Invalid masked card number format")
            return card_number
        
        # Validate full card number
        if not re.match(r'^\d{13,19}$', cleaned_number):
            raise ValidationException("Card number must be 13-19 digits")
        
        # Basic Luhn algorithm check
        if not FinancialValidators._luhn_check(cleaned_number):
            raise ValidationException("Invalid card number (failed Luhn check)")
        
        return cleaned_number
    
    @staticmethod
    def _luhn_check(card_number: str) -> bool:
        """Validate card number using Luhn algorithm."""
        def luhn_digit(n):
            return n if n < 10 else n - 9
        
        digits = [int(d) for d in card_number]
        odd_sum = sum(digits[-1::-2])
        even_sum = sum(luhn_digit(2 * d) for d in digits[-2::-2])
        
        return (odd_sum + even_sum) % 10 == 0
    
    @staticmethod
    def validate_phone_number(phone: str) -> str:
        """Validate phone number format."""
        if not isinstance(phone, str):
            raise ValidationException("Phone number must be a string")
        
        phone = phone.strip()
        
        # Remove formatting characters
        cleaned_phone = re.sub(r'[\s\-\(\)\+]', '', phone)
        
        # Check if it's all digits (possibly with leading +)
        if not re.match(r'^\+?\d{10,15}$', cleaned_phone):
            raise ValidationException("Phone number must be 10-15 digits, optionally starting with +")
        
        return phone
    
    @staticmethod
    def validate_email(email: str) -> str:
        """Validate email format."""
        if not isinstance(email, str):
            raise ValidationException("Email must be a string")
        
        email = email.strip().lower()
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValidationException("Invalid email format")
        
        return email
    
    @staticmethod
    def validate_date_range(start_date: Any, end_date: Any) -> tuple[datetime, datetime]:
        """Validate date range."""
        # Convert to datetime if needed
        if isinstance(start_date, date) and not isinstance(start_date, datetime):
            start_date = datetime.combine(start_date, datetime.min.time())
        elif isinstance(start_date, str):
            try:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise ValidationException(f"Invalid start date format: {start_date}")
        
        if isinstance(end_date, date) and not isinstance(end_date, datetime):
            end_date = datetime.combine(end_date, datetime.max.time())
        elif isinstance(end_date, str):
            try:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise ValidationException(f"Invalid end date format: {end_date}")
        
        # Validate range
        if start_date >= end_date:
            raise ValidationException("Start date must be before end date")
        
        # Check if range is too large (e.g., more than 2 years)
        if (end_date - start_date).days > 730:
            raise ValidationException("Date range cannot exceed 2 years")
        
        return start_date, end_date
    
    @staticmethod
    def validate_pagination_params(page: int, page_size: int) -> tuple[int, int]:
        """Validate pagination parameters."""
        if page < 1:
            raise ValidationException("Page number must be 1 or greater")
        
        if page_size < 1:
            raise ValidationException("Page size must be 1 or greater")
        
        if page_size > 100:
            raise ValidationException("Page size cannot exceed 100")
        
        return page, page_size
    
    @staticmethod
    def validate_percentage(percentage: Any, min_pct: Decimal = Decimal("0"), max_pct: Decimal = Decimal("100")) -> Decimal:
        """Validate percentage value."""
        try:
            if isinstance(percentage, str):
                # Remove % symbol if present
                cleaned_pct = percentage.replace('%', '').strip()
                decimal_pct = Decimal(cleaned_pct)
            elif isinstance(percentage, (int, float)):
                decimal_pct = Decimal(str(percentage))
            elif isinstance(percentage, Decimal):
                decimal_pct = percentage
            else:
                raise ValidationException(f"Invalid percentage format: {percentage}")
            
            if decimal_pct < min_pct or decimal_pct > max_pct:
                raise ValidationException(f"Percentage {decimal_pct} must be between {min_pct} and {max_pct}")
            
            return decimal_pct
            
        except (InvalidOperation, ValueError):
            raise ValidationException(f"Invalid percentage format: {percentage}")


class BusinessRuleValidator:
    """Validator for business rules and constraints."""
    
    @staticmethod
    def validate_transfer_amount(
        amount: Decimal,
        available_balance: Decimal,
        daily_limit: Decimal,
        current_daily_spent: Decimal,
        min_transfer: Decimal = Decimal("1.00"),
        max_transfer: Decimal = Decimal("100000.00")
    ) -> bool:
        """Validate transfer amount against multiple constraints."""
        
        # Check minimum/maximum limits
        if amount < min_transfer:
            raise ValidationException(f"Transfer amount {amount} is below minimum {min_transfer}")
        
        if amount > max_transfer:
            raise ValidationException(f"Transfer amount {amount} exceeds maximum {max_transfer}")
        
        # Check sufficient balance
        if amount > available_balance:
            raise ValidationException(f"Insufficient balance. Available: {available_balance}, Requested: {amount}")
        
        # Check daily limits
        projected_daily_spent = current_daily_spent + amount
        if projected_daily_spent > daily_limit:
            raise ValidationException(f"Transfer would exceed daily limit. Limit: {daily_limit}, Current spent: {current_daily_spent}")
        
        return True
    
    @staticmethod
    def validate_investment_amount(
        amount: Decimal,
        available_cash: Decimal,
        stock_price: Decimal,
        min_investment: Decimal = Decimal("10.00")
    ) -> bool:
        """Validate investment transaction amount."""
        
        if amount < min_investment:
            raise ValidationException(f"Investment amount {amount} is below minimum {min_investment}")
        
        if amount > available_cash:
            raise ValidationException(f"Insufficient cash. Available: {available_cash}, Requested: {amount}")
        
        # Check if amount allows for at least partial share purchase
        if amount < stock_price:
            raise ValidationException(f"Investment amount {amount} is less than stock price {stock_price}")
        
        return True
    
    @staticmethod
    def validate_savings_goal(
        target_amount: Decimal,
        current_amount: Decimal,
        target_date: datetime,
        monthly_contribution: Decimal
    ) -> bool:
        """Validate savings goal parameters."""
        
        if target_amount <= current_amount:
            raise ValidationException("Target amount must be greater than current amount")
        
        if target_date <= datetime.now():
            raise ValidationException("Target date must be in the future")
        
        if monthly_contribution < 0:
            raise ValidationException("Monthly contribution cannot be negative")
        
        # Check if goal is achievable with given contribution
        months_remaining = (target_date.year - datetime.now().year) * 12 + (target_date.month - datetime.now().month)
        if months_remaining <= 0:
            raise ValidationException("Target date must be at least 1 month in the future")
        
        amount_needed = target_amount - current_amount
        total_contributions = monthly_contribution * months_remaining
        
        if total_contributions < amount_needed:
            required_monthly = amount_needed / months_remaining
            raise ValidationException(
                f"Monthly contribution {monthly_contribution} is insufficient. "
                f"Required: {required_monthly.quantize(Decimal('0.01'))}"
            )
        
        return True


def validate_user_id(user_id: str) -> str:
    """Validate user ID format."""
    if not isinstance(user_id, str):
        raise ValidationException("User ID must be a string")
    
    user_id = user_id.strip()
    
    if not user_id:
        raise ValidationException("User ID cannot be empty")
    
    if len(user_id) < 3 or len(user_id) > 50:
        raise ValidationException("User ID must be 3-50 characters long")
    
    # Check format (alphanumeric with underscores)
    if not re.match(r'^[a-zA-Z0-9_]+$', user_id):
        raise ValidationException("User ID must contain only letters, numbers, and underscores")
    
    return user_id


def validate_search_term(search_term: str) -> str:
    """Validate search term."""
    if not isinstance(search_term, str):
        raise ValidationException("Search term must be a string")
    
    search_term = search_term.strip()
    
    if not search_term:
        raise ValidationException("Search term cannot be empty")
    
    if len(search_term) < 2:
        raise ValidationException("Search term must be at least 2 characters long")
    
    if len(search_term) > 100:
        raise ValidationException("Search term cannot exceed 100 characters")
    
    return search_term


def validate_transaction_id(transaction_id: str) -> str:
    """Validate transaction ID format."""
    if not isinstance(transaction_id, str):
        raise ValidationException("Transaction ID must be a string")
    
    transaction_id = transaction_id.strip()
    
    if not transaction_id:
        raise ValidationException("Transaction ID cannot be empty")
    
    # Transaction IDs typically follow a specific pattern
    if not re.match(r'^[A-Z0-9_-]+$', transaction_id.upper()):
        raise ValidationException("Transaction ID contains invalid characters")
    
    return transaction_id.upper()


def validate_stock_symbol(symbol: str) -> str:
    """Validate stock symbol format."""
    if not isinstance(symbol, str):
        raise ValidationException("Stock symbol must be a string")
    
    symbol = symbol.upper().strip()
    
    if not symbol:
        raise ValidationException("Stock symbol cannot be empty")
    
    # Stock symbols are typically 1-5 letters
    if not re.match(r'^[A-Z]{1,5}$', symbol):
        raise ValidationException("Stock symbol must be 1-5 letters")
    
    return symbol


def validate_goal_name(goal_name: str) -> str:
    """Validate savings goal name."""
    if not isinstance(goal_name, str):
        raise ValidationException("Goal name must be a string")
    
    goal_name = goal_name.strip()
    
    if not goal_name:
        raise ValidationException("Goal name cannot be empty")
    
    if len(goal_name) < 2:
        raise ValidationException("Goal name must be at least 2 characters long")
    
    if len(goal_name) > 50:
        raise ValidationException("Goal name cannot exceed 50 characters")
    
    # Check for valid characters (letters, numbers, spaces, basic punctuation)
    if not re.match(r'^[a-zA-Z0-9\s\-\._\'\"!]+$', goal_name):
        raise ValidationException("Goal name contains invalid characters")
    
    return goal_name


def validate_beneficiary_details(account_number: str, bank_code: Optional[str] = None, country: str = "US") -> Dict[str, str]:
    """Validate beneficiary account details."""
    validated_account = validate_account_number(account_number)
    
    result = {
        "account_number": validated_account,
        "country": country.upper()
    }
    
    if bank_code:
        bank_code = bank_code.strip().upper()
        
        if country.upper() == "US":
            # US routing number validation (9 digits)
            if not re.match(r'^\d{9}$', bank_code):
                raise ValidationException("US routing number must be 9 digits")
        elif country.upper() in ["GB", "EU"]:
            # IBAN validation (simplified)
            if not re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]+$', bank_code):
                raise ValidationException("Invalid IBAN format")
        else:
            # Generic bank code validation
            if not re.match(r'^[A-Z0-9]{4,11}$', bank_code):
                raise ValidationException("Bank code must be 4-11 alphanumeric characters")
        
        result["bank_code"] = bank_code
    
    return result


class CardValidator:
    """Specialized validator for card-related operations."""
    
    @staticmethod
    def validate_cvv(cvv: str, card_type: str = "unknown") -> str:
        """Validate CVV code."""
        if not isinstance(cvv, str):
            raise ValidationException("CVV must be a string")
        
        cvv = cvv.strip()
        
        # American Express uses 4 digits, others use 3
        if card_type.lower() in ["amex", "american express"]:
            if not re.match(r'^\d{4}$', cvv):
                raise ValidationException("American Express CVV must be 4 digits")
        else:
            if not re.match(r'^\d{3}$', cvv):
                raise ValidationException("CVV must be 3 digits")
        
        return cvv
    
    @staticmethod
    def validate_expiry_date(expiry: str) -> str:
        """Validate card expiry date."""
        if not isinstance(expiry, str):
            raise ValidationException("Expiry date must be a string")
        
        expiry = expiry.strip()
        
        # Accept MM/YY or MM/YYYY formats
        if re.match(r'^\d{2}/\d{2}$', expiry):
            month, year = expiry.split('/')
            year = f"20{year}"  # Convert YY to 20YY
        elif re.match(r'^\d{2}/\d{4}$', expiry):
            month, year = expiry.split('/')
        else:
            raise ValidationException("Expiry date must be in MM/YY or MM/YYYY format")
        
        # Validate month
        if not 1 <= int(month) <= 12:
            raise ValidationException("Invalid month in expiry date")
        
        # Validate year (must be current year or later)
        current_year = datetime.now().year
        expiry_year = int(year)
        
        if expiry_year < current_year:
            raise ValidationException("Card has expired")
        
        # Check if expiry is not too far in the future (10 years)
        if expiry_year > current_year + 10:
            raise ValidationException("Expiry date too far in the future")
        
        return f"{month}/{year[-2:]}"  # Return in MM/YY format
    
    @staticmethod
    def validate_pin(pin: str) -> bool:
        """Validate PIN format (don't return the actual PIN for security)."""
        if not isinstance(pin, str):
            raise ValidationException("PIN must be a string")
        
        pin = pin.strip()
        
        if not re.match(r'^\d{4,6}$', pin):
            raise ValidationException("PIN must be 4-6 digits")
        
        # Check for common weak PINs
        weak_pins = ["0000", "1234", "1111", "2222", "3333", "4444", "5555", "6666", "7777", "8888", "9999"]
        if pin in weak_pins:
            raise ValidationException("PIN is too weak, please choose a more secure PIN")
        
        return True  # Don't return the actual PIN


def sanitize_input(input_str: str, max_length: int = 255, allow_html: bool = False) -> str:
    """Sanitize user input for security."""
    if not isinstance(input_str, str):
        return str(input_str)
    
    # Trim whitespace
    sanitized = input_str.strip()
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # Remove HTML tags if not allowed
    if not allow_html:
        sanitized = re.sub(r'<[^>]+>', '', sanitized)
    
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', sanitized)
    
    return sanitized
