"""
Currency conversion utilities with mock exchange rates.
"""
import random
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
from datetime import datetime, UTC

from ..config.settings import Settings
from ..core.exceptions import InvalidCurrencyException


class CurrencyConverter:
    """Currency conversion utility with mock exchange rates."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_currency = settings.default_currency
        self.supported_currencies = settings.supported_currencies
        
        # Mock exchange rates (rates to USD)
        self._mock_rates = {
            "USD": Decimal("1.0000"),
            "EUR": Decimal("0.8500"),
            "GBP": Decimal("0.7800"),
            "KES": Decimal("147.5000"),
            "UGX": Decimal("3750.0000"),
            "TZS": Decimal("2500.0000"),
        }
    
    async def get_exchange_rate(self, from_currency: str, to_currency: str) -> Decimal:
        """Get exchange rate between two currencies."""
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        # Validate currencies
        if from_currency not in self.supported_currencies:
            raise InvalidCurrencyException(from_currency, self.supported_currencies)
        
        if to_currency not in self.supported_currencies:
            raise InvalidCurrencyException(to_currency, self.supported_currencies)
        
        # Same currency
        if from_currency == to_currency:
            return Decimal("1.0000")
        
        # Get rates (all rates are relative to USD)
        from_rate = self._mock_rates.get(from_currency, Decimal("1.0000"))
        to_rate = self._mock_rates.get(to_currency, Decimal("1.0000"))
        
        # Calculate cross rate with some random variation to simulate real markets
        base_rate = to_rate / from_rate
        variation = Decimal(str(random.uniform(0.995, 1.005)))  # ±0.5% variation
        
        rate = (base_rate * variation).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return rate
    
    async def convert_amount(
        self, 
        amount: Decimal, 
        from_currency: str, 
        to_currency: str
    ) -> Decimal:
        """Convert amount from one currency to another."""
        rate = await self.get_exchange_rate(from_currency, to_currency)
        converted = (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return converted
    
    async def get_all_rates(self, base_currency: str = "USD") -> Dict[str, Decimal]:
        """Get exchange rates for all supported currencies."""
        base_currency = base_currency.upper()
        
        if base_currency not in self.supported_currencies:
            raise InvalidCurrencyException(base_currency, self.supported_currencies)
        
        rates = {}
        for currency in self.supported_currencies:
            if currency != base_currency:
                rates[currency] = await self.get_exchange_rate(base_currency, currency)
            else:
                rates[currency] = Decimal("1.0000")
        
        return rates
    
    def is_currency_supported(self, currency: str) -> bool:
        """Check if a currency is supported."""
        return currency.upper() in self.supported_currencies
    
    def format_currency(self, amount: Decimal, currency: str) -> str:
        """Format currency amount for display."""
        currency = currency.upper()
        
        # Currency symbols
        symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "KES": "KSh",
            "UGX": "USh",
            "TZS": "TSh",
        }
        
        symbol = symbols.get(currency, currency)
        
        # Format based on currency
        if currency in ["KES", "UGX", "TZS"]:
            # No decimal places for these currencies
            formatted_amount = f"{amount:,.0f}"
        else:
            # Two decimal places for major currencies
            formatted_amount = f"{amount:,.2f}"
        
        return f"{symbol}{formatted_amount}"


# Global converter instance
_converter: Optional[CurrencyConverter] = None


def get_currency_converter(settings: Optional[Settings] = None) -> CurrencyConverter:
    """Get the global currency converter instance."""
    global _converter
    
    if _converter is None:
        if settings is None:
            from ..config.settings import get_settings
            settings = get_settings()
        _converter = CurrencyConverter(settings)
    
    return _converter


async def convert_currency(
    amount: Decimal, 
    from_currency: str, 
    to_currency: str,
    converter: Optional[CurrencyConverter] = None
) -> Decimal:
    """Convenience function for currency conversion."""
    if converter is None:
        converter = get_currency_converter()
    
    return await converter.convert_amount(amount, from_currency, to_currency)


def validate_currency_code(currency: str, supported_currencies: List[str]) -> str:
    """Validate and normalize currency code."""
    currency = currency.upper().strip()
    
    if len(currency) != 3:
        raise InvalidCurrencyException(currency, supported_currencies)
    
    if currency not in supported_currencies:
        raise InvalidCurrencyException(currency, supported_currencies)
    
    return currency
