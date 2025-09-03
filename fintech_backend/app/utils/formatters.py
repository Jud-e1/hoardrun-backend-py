"""
Response formatting utilities for consistent API responses.
"""
from decimal import Decimal
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from ..models.base import BaseResponse, PaginatedResponse, ErrorResponse
from ..config.logging import get_correlation_id


class ResponseFormatter:
    """Utility class for formatting API responses consistently."""
    
    @staticmethod
    def success_response(
        data: Any,
        message: Optional[str] = None,
        status_code: int = 200
    ) -> Dict[str, Any]:
        """Format a successful API response."""
        response = {
            "status": "success",
            "data": ResponseFormatter._format_data(data),
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": get_correlation_id()
        }
        
        if message:
            response["message"] = message
        
        return response
    
    @staticmethod
    def paginated_response(
        data: List[Any],
        page: int,
        page_size: int,
        total_items: int,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format a paginated API response."""
        total_pages = (total_items + page_size - 1) // page_size
        
        response = {
            "status": "success",
            "data": [ResponseFormatter._format_data(item) for item in data],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1
            },
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": get_correlation_id()
        }
        
        if message:
            response["message"] = message
        
        return response
    
    @staticmethod
    def error_response(
        message: str,
        error_code: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Format an error API response."""
        response = {
            "status": "error",
            "message": message,
            "error_code": error_code,
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": get_correlation_id()
        }
        
        if details:
            response["details"] = details
        
        return response
    
    @staticmethod
    def _format_data(data: Any) -> Any:
        """Format data for JSON serialization."""
        if isinstance(data, dict):
            formatted = {}
            for key, value in data.items():
                formatted[key] = ResponseFormatter._format_data(value)
            return formatted
        
        elif isinstance(data, list):
            return [ResponseFormatter._format_data(item) for item in data]
        
        elif isinstance(data, Decimal):
            return float(data)
        
        elif isinstance(data, datetime):
            return data.isoformat()
        
        elif hasattr(data, 'dict'):  # Pydantic models
            return ResponseFormatter._format_data(data.dict())
        
        elif hasattr(data, '__dict__'):  # Other objects
            return ResponseFormatter._format_data(data.__dict__)
        
        else:
            return data


class FinancialFormatter:
    """Specialized formatter for financial data."""
    
    @staticmethod
    def format_currency_amount(amount: Decimal, currency: str = "USD") -> Dict[str, Any]:
        """Format currency amount with symbol and display text."""
        # Currency symbols
        symbols = {
            "USD": "$",
            "EUR": "€", 
            "GBP": "£",
            "KES": "KSh",
            "UGX": "USh",
            "TZS": "TSh"
        }
        
        symbol = symbols.get(currency.upper(), currency)
        
        # Format based on currency
        if currency.upper() in ["KES", "UGX", "TZS"]:
            # No decimal places for these currencies
            formatted_amount = f"{amount:,.0f}"
            raw_amount = float(amount)
        else:
            # Two decimal places for major currencies
            formatted_amount = f"{amount:,.2f}"
            raw_amount = float(amount)
        
        return {
            "amount": raw_amount,
            "currency": currency.upper(),
            "formatted": f"{symbol}{formatted_amount}",
            "symbol": symbol
        }
    
    @staticmethod
    def format_percentage(value: Decimal, decimal_places: int = 2) -> Dict[str, Any]:
        """Format percentage for display."""
        return {
            "value": float(value),
            "formatted": f"{value:.{decimal_places}f}%",
            "decimal_places": decimal_places
        }
    
    @staticmethod
    def format_account_summary(account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format account data for API response."""
        formatted = {
            "account_id": account_data.get("id"),
            "account_type": account_data.get("account_type"),
            "account_name": account_data.get("account_name"),
            "account_number": FinancialFormatter._mask_account_number(account_data.get("account_number", "")),
            "balance": FinancialFormatter.format_currency_amount(
                account_data.get("balance", Decimal("0")),
                account_data.get("currency", "USD")
            ),
            "available_balance": FinancialFormatter.format_currency_amount(
                account_data.get("available_balance", Decimal("0")),
                account_data.get("currency", "USD")
            ),
            "status": account_data.get("status"),
            "bank_name": account_data.get("bank_name"),
            "last_updated": account_data.get("updated_at")
        }
        
        # Add interest rate for savings accounts
        if account_data.get("account_type") == "savings":
            formatted["interest_rate"] = FinancialFormatter.format_percentage(
                account_data.get("interest_rate", Decimal("0"))
            )
        
        return formatted
    
    @staticmethod
    def format_card_summary(card_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format card data for API response."""
        return {
            "card_id": card_data.get("id"),
            "card_number": card_data.get("card_number"),  # Already masked
            "card_type": card_data.get("card_type"),
            "brand": card_data.get("brand"),
            "card_name": card_data.get("card_name"),
            "status": card_data.get("status"),
            "expiry_date": card_data.get("expiry_date"),
            "is_frozen": card_data.get("is_frozen", False),
            "limits": {
                "daily": FinancialFormatter.format_currency_amount(
                    card_data.get("daily_limit", Decimal("0")), "USD"
                ),
                "monthly": FinancialFormatter.format_currency_amount(
                    card_data.get("monthly_limit", Decimal("0")), "USD"
                ),
                "daily_spent": FinancialFormatter.format_currency_amount(
                    card_data.get("current_daily_spent", Decimal("0")), "USD"
                ),
                "monthly_spent": FinancialFormatter.format_currency_amount(
                    card_data.get("current_monthly_spent", Decimal("0")), "USD"
                )
            }
        }
    
    @staticmethod
    def format_transaction(transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format transaction data for API response."""
        return {
            "transaction_id": transaction_data.get("id"),
            "amount": FinancialFormatter.format_currency_amount(
                transaction_data.get("amount", Decimal("0")),
                transaction_data.get("currency", "USD")
            ),
            "transaction_type": transaction_data.get("transaction_type"),
            "category": transaction_data.get("category"),
            "merchant": transaction_data.get("merchant"),
            "description": transaction_data.get("description"),
            "date": transaction_data.get("transaction_date"),
            "status": transaction_data.get("status"),
            "reference_number": transaction_data.get("reference_number"),
            "location": transaction_data.get("location"),
            "account_id": transaction_data.get("account_id"),
            "card_id": transaction_data.get("card_id"),
            "is_recurring": transaction_data.get("is_recurring", False)
        }
    
    @staticmethod
    def format_investment_holding(holding_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format investment holding for API response."""
        shares = holding_data.get("shares", Decimal("0"))
        current_price = holding_data.get("current_price", Decimal("0"))
        avg_purchase_price = holding_data.get("avg_purchase_price", Decimal("0"))
        
        market_value = shares * current_price
        cost_basis = shares * avg_purchase_price
        gain_loss = market_value - cost_basis
        gain_loss_pct = (gain_loss / cost_basis * 100) if cost_basis > 0 else Decimal("0")
        
        return {
            "symbol": holding_data.get("symbol"),
            "company_name": holding_data.get("company_name"),
            "shares": float(shares),
            "current_price": FinancialFormatter.format_currency_amount(current_price, "USD"),
            "avg_purchase_price": FinancialFormatter.format_currency_amount(avg_purchase_price, "USD"),
            "market_value": FinancialFormatter.format_currency_amount(market_value, "USD"),
            "cost_basis": FinancialFormatter.format_currency_amount(cost_basis, "USD"),
            "unrealized_gain_loss": {
                **FinancialFormatter.format_currency_amount(gain_loss, "USD"),
                "percentage": FinancialFormatter.format_percentage(gain_loss_pct)
            },
            "purchase_date": holding_data.get("purchase_date")
        }
    
    @staticmethod
    def format_savings_goal(goal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format savings goal for API response."""
        target_amount = goal_data.get("target_amount", Decimal("0"))
        current_amount = goal_data.get("current_amount", Decimal("0"))
        progress_pct = (current_amount / target_amount * 100) if target_amount > 0 else Decimal("0")
        
        return {
            "goal_id": goal_data.get("id"),
            "goal_name": goal_data.get("goal_name"),
            "target_amount": FinancialFormatter.format_currency_amount(target_amount, "USD"),
            "current_amount": FinancialFormatter.format_currency_amount(current_amount, "USD"),
            "progress_percentage": FinancialFormatter.format_percentage(progress_pct),
            "target_date": goal_data.get("target_date"),
            "monthly_contribution": FinancialFormatter.format_currency_amount(
                goal_data.get("monthly_contribution", Decimal("0")), "USD"
            ),
            "auto_save_enabled": goal_data.get("auto_save_enabled", False),
            "auto_save_settings": {
                "amount": FinancialFormatter.format_currency_amount(
                    goal_data.get("auto_save_amount", Decimal("0")), "USD"
                ),
                "frequency": goal_data.get("auto_save_frequency", "none")
            }
        }
    
    @staticmethod
    def _mask_account_number(account_number: str) -> str:
        """Mask account number for security."""
        if len(account_number) <= 4:
            return "*" * len(account_number)
        
        # Show last 4 digits
        masked = "*" * (len(account_number) - 4) + account_number[-4:]
        return masked
    
    @staticmethod
    def _mask_card_number(card_number: str) -> str:
        """Mask card number for security."""
        if len(card_number) <= 4:
            return "*" * len(card_number)
        
        # Format as ****-****-****-1234
        if len(card_number) >= 16:
            return f"****-****-****-{card_number[-4:]}"
        else:
            return "*" * (len(card_number) - 4) + card_number[-4:]


class DashboardFormatter:
    """Specialized formatter for dashboard data."""
    
    @staticmethod
    def format_financial_summary(
        total_balance: Decimal,
        available_balance: Decimal,
        total_assets: Decimal,
        total_liabilities: Decimal,
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """Format financial summary for dashboard."""
        net_worth = total_assets - total_liabilities
        
        return {
            "balances": {
                "total_balance": FinancialFormatter.format_currency_amount(total_balance, currency),
                "available_balance": FinancialFormatter.format_currency_amount(available_balance, currency),
                "net_worth": FinancialFormatter.format_currency_amount(net_worth, currency)
            },
            "assets": {
                "total_assets": FinancialFormatter.format_currency_amount(total_assets, currency),
                "cash_and_equivalents": FinancialFormatter.format_currency_amount(total_balance, currency),
                "investments": FinancialFormatter.format_currency_amount(
                    total_assets - total_balance, currency
                )
            },
            "liabilities": {
                "total_liabilities": FinancialFormatter.format_currency_amount(total_liabilities, currency)
            }
        }
    
    @staticmethod
    def format_spending_analytics(
        monthly_spending: Decimal,
        category_breakdown: List[Dict],
        spending_trends: List[Dict],
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """Format spending analytics for dashboard."""
        return {
            "summary": {
                "monthly_spending": FinancialFormatter.format_currency_amount(monthly_spending, currency),
                "top_category": category_breakdown[0]["category"] if category_breakdown else "None",
                "total_transactions": sum(cat.get("transaction_count", 0) for cat in category_breakdown)
            },
            "category_breakdown": [
                {
                    "category": cat["category"],
                    "amount": FinancialFormatter.format_currency_amount(cat["amount"], currency),
                    "percentage": FinancialFormatter.format_percentage(cat["percentage"]),
                    "transaction_count": cat["transaction_count"]
                }
                for cat in category_breakdown
            ],
            "monthly_trends": [
                {
                    "month": trend["month"],
                    "spending": FinancialFormatter.format_currency_amount(trend["total_spending"], currency),
                    "transaction_count": trend["transaction_count"],
                    "avg_transaction": FinancialFormatter.format_currency_amount(
                        trend["avg_transaction_amount"], currency
                    )
                }
                for trend in spending_trends
            ]
        }
    
    @staticmethod
    def format_recent_activity(transactions: List[Dict], limit: int = 5) -> List[Dict[str, Any]]:
        """Format recent transactions for dashboard."""
        return [
            {
                "transaction_id": tx.get("id"),
                "amount": FinancialFormatter.format_currency_amount(
                    tx.get("amount", Decimal("0")),
                    tx.get("currency", "USD")
                ),
                "type": tx.get("transaction_type"),
                "merchant": tx.get("merchant"),
                "category": tx.get("category"),
                "date": tx.get("transaction_date"),
                "status": tx.get("status")
            }
            for tx in transactions[:limit]
        ]


class NotificationFormatter:
    """Formatter for notification data."""
    
    @staticmethod
    def format_notification(notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format notification for API response."""
        return {
            "notification_id": notification_data.get("id"),
            "type": notification_data.get("type"),
            "title": notification_data.get("title"),
            "message": notification_data.get("message"),
            "priority": notification_data.get("priority", "normal"),
            "is_read": notification_data.get("is_read", False),
            "created_at": notification_data.get("created_at"),
            "data": notification_data.get("data", {}),
            "action_required": notification_data.get("action_required", False)
        }
    
    @staticmethod
    def create_transaction_notification(
        transaction: Dict[str, Any],
        notification_type: str = "transaction_alert"
    ) -> Dict[str, Any]:
        """Create a notification for a transaction."""
        amount = transaction.get("amount", Decimal("0"))
        currency = transaction.get("currency", "USD")
        merchant = transaction.get("merchant", "Unknown")
        
        formatted_amount = FinancialFormatter.format_currency_amount(amount, currency)
        
        return {
            "type": notification_type,
            "title": "Transaction Alert",
            "message": f"Transaction of {formatted_amount['formatted']} at {merchant}",
            "priority": "normal",
            "is_read": False,
            "data": {
                "transaction_id": transaction.get("id"),
                "amount": formatted_amount,
                "merchant": merchant,
                "category": transaction.get("category")
            },
            "action_required": False
        }
    
    @staticmethod
    def create_limit_alert(
        current_spent: Decimal,
        limit: Decimal,
        limit_type: str,
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """Create a spending limit alert notification."""
        utilization = (current_spent / limit * 100) if limit > 0 else Decimal("0")
        formatted_spent = FinancialFormatter.format_currency_amount(current_spent, currency)
        formatted_limit = FinancialFormatter.format_currency_amount(limit, currency)
        
        return {
            "type": "spending_limit_alert",
            "title": f"{limit_type.title()} Spending Alert",
            "message": f"You've spent {formatted_spent['formatted']} of your {formatted_limit['formatted']} {limit_type} limit",
            "priority": "high" if utilization >= 90 else "normal",
            "is_read": False,
            "data": {
                "current_spent": formatted_spent,
                "limit": formatted_limit,
                "utilization_percentage": FinancialFormatter.format_percentage(utilization),
                "limit_type": limit_type
            },
            "action_required": utilization >= 90
        }


class MetricsFormatter:
    """Formatter for performance and business metrics."""
    
    @staticmethod
    def format_performance_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Format performance metrics for monitoring."""
        return {
            "response_times": {
                "avg_response_time_ms": round(metrics.get("avg_response_time", 0), 2),
                "p95_response_time_ms": round(metrics.get("p95_response_time", 0), 2),
                "p99_response_time_ms": round(metrics.get("p99_response_time", 0), 2)
            },
            "request_counts": {
                "total_requests": metrics.get("total_requests", 0),
                "successful_requests": metrics.get("successful_requests", 0),
                "failed_requests": metrics.get("failed_requests", 0),
                "success_rate": FinancialFormatter.format_percentage(
                    metrics.get("success_rate", Decimal("0"))
                )
            },
            "business_metrics": {
                "total_transactions": metrics.get("total_transactions", 0),
                "total_volume": FinancialFormatter.format_currency_amount(
                    metrics.get("total_volume", Decimal("0")), "USD"
                ),
                "active_users": metrics.get("active_users", 0)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
