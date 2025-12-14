"""
Account management service - Plaid-based implementation.
Now uses Plaid as the primary source for account data.
"""

import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any

from ..models.account import (
    AccountBalance, AccountStatement, StatementTransaction, 
    TransactionCategory, StatementRequest, BalanceHistoryRequest, 
    BalanceHistoryPoint
)
from ..core.exceptions import (
    ValidationError, NotFoundError, BusinessLogicError,
    UnauthorizedError
)
from ..data.repository import get_repository_manager
from ..utils.validators import validate_user_exists
from ..config.logging import get_logger
from .plaid_service import get_plaid_service

logger = get_logger(__name__)


class AccountService:
    """Service for managing financial accounts via Plaid."""
    
    def __init__(self):
        self.repo = get_repository_manager()
        self.plaid_service = get_plaid_service()
    
    async def list_user_accounts(
        self, 
        user_id: str,
        account_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List all Plaid accounts for a user with optional filtering.
        
        Args:
            user_id: User identifier
            account_type: Optional account type filter
            status: Optional status filter
            
        Returns:
            Dictionary with accounts list and metadata
        """
        logger.info(f"Listing Plaid accounts for user {user_id}")
        
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        
        # Get all Plaid accounts for user
        plaid_accounts = await self.plaid_service.get_user_accounts(user_id)
        
        # Apply filters
        filtered_accounts = []
        primary_account_id = None
        
        for account in plaid_accounts:
            if account_type and account.type != account_type:
                continue
            if status and account.status != status:
                continue
                
            filtered_accounts.append(account)
            
            # First account is considered primary
            if not primary_account_id:
                primary_account_id = account.account_id
        
        logger.info(f"Found {len(filtered_accounts)} Plaid accounts for user {user_id}")
        return {
            "accounts": filtered_accounts,
            "total_count": len(filtered_accounts),
            "primary_account_id": primary_account_id
        }
    
    async def get_account_details(self, account_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific Plaid account.
        
        Args:
            account_id: Plaid account identifier
            user_id: User identifier
            
        Returns:
            Account details from Plaid
        """
        logger.info(f"Getting Plaid account details for {account_id}")
        
        plaid_accounts = await self.plaid_service.get_user_accounts(user_id)
        account = next((acc for acc in plaid_accounts if acc.account_id == account_id), None)
        
        if not account:
            raise NotFoundError(f"Plaid account {account_id} not found")
        
        return account
    
    async def get_account_balance(self, account_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get current account balance from Plaid.
        
        Args:
            account_id: Plaid account identifier
            user_id: User identifier
            
        Returns:
            Current balance information from Plaid
        """
        logger.info(f"Getting balance for Plaid account {account_id}")
        
        account = await self.get_account_details(account_id, user_id)
        
        return {
            "account_id": account_id,
            "balance": account.balances,
            "last_updated": account.updated_at
        }
    
    async def generate_statement(
        self, 
        account_id: str, 
        user_id: str, 
        request: StatementRequest
    ) -> Dict[str, Any]:
        """
        Generate account statement from Plaid transaction data.
        
        Args:
            account_id: Plaid account identifier
            user_id: User identifier
            request: Statement generation request
            
        Returns:
            Generated statement with Plaid transactions
        """
        logger.info(f"Generating statement for Plaid account {account_id}")
        
        account = await self.get_account_details(account_id, user_id)
        
        # Validate date range
        if request.end_date > date.today():
            raise ValidationError("End date cannot be in the future")
        
        # Get Plaid connection for this account
        plaid_accounts = await self.plaid_service.get_user_accounts(user_id)
        plaid_account = next((acc for acc in plaid_accounts if acc.account_id == account_id), None)
        
        if not plaid_account:
            raise NotFoundError("Plaid account not found")
        
        # Get transactions from Plaid for the period
        connection = await self.repo.get_plaid_connection(plaid_account.connection_id)
        transactions = await self.repo.get_plaid_transactions_by_date_range(
            connection.connection_id,
            request.start_date,
            request.end_date
        )
        
        # Filter transactions for this account
        account_transactions = [t for t in transactions if t.account_id == account_id]
        
        # Calculate statement summary
        total_credits = sum(abs(t.amount) for t in account_transactions if t.amount < 0)  # Plaid uses negative for credits
        total_debits = sum(t.amount for t in account_transactions if t.amount > 0)  # Plaid uses positive for debits
        
        # Get opening balance (current balance minus net change)
        net_change = total_credits - total_debits
        closing_balance = account.balances.get("current", Decimal("0"))
        opening_balance = closing_balance - net_change
        
        # Create statement
        statement_id = str(uuid.uuid4())
        statement = AccountStatement(
            statement_id=statement_id,
            account_id=account_id,
            statement_period_start=request.start_date,
            statement_period_end=request.end_date,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits,
            transaction_count=len(account_transactions),
            generated_at=datetime.utcnow()
        )
        
        # Convert Plaid transactions to statement format
        statement_transactions = []
        running_balance = opening_balance
        
        for transaction in sorted(account_transactions, key=lambda x: x.date):
            # Plaid uses positive for debits, negative for credits
            amount = -transaction.amount  # Flip sign for statement
            running_balance += amount
            
            statement_transactions.append(StatementTransaction(
                transaction_id=transaction.transaction_id,
                date=transaction.date,
                description=transaction.name,
                category=TransactionCategory.OTHER,
                amount=amount,
                balance_after=running_balance,
                reference_number=transaction.transaction_id
            ))
        
        # Calculate summary by category
        summary = self._calculate_statement_summary(statement_transactions)
        
        logger.info(f"Statement generated for Plaid account {account_id}: {len(statement_transactions)} transactions")
        return {
            "statement": statement,
            "transactions": statement_transactions,
            "summary": summary
        }
    
    async def get_balance_history(
        self, 
        account_id: str, 
        user_id: str, 
        request: BalanceHistoryRequest
    ) -> Dict[str, Any]:
        """
        Get account balance history from Plaid data.
        
        Args:
            account_id: Plaid account identifier
            user_id: User identifier
            request: Balance history request
            
        Returns:
            Balance history data and trend analysis
        """
        logger.info(f"Getting balance history for Plaid account {account_id}")
        
        account = await self.get_account_details(account_id, user_id)
        
        # Calculate period
        end_date = date.today()
        start_date = end_date - timedelta(days=request.days)
        
        history_points = await self._generate_balance_history_from_plaid(
            account_id, user_id, start_date, end_date, request.granularity
        )
        
        # Calculate trend and average
        if len(history_points) >= 2:
            first_balance = history_points[0].balance
            last_balance = history_points[-1].balance
            
            if last_balance > first_balance * Decimal("1.05"):
                trend = "increasing"
            elif last_balance < first_balance * Decimal("0.95"):
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        average_balance = (
            sum(point.balance for point in history_points) / len(history_points)
            if history_points else Decimal("0")
        )
        
        return {
            "account_id": account_id,
            "period_start": start_date,
            "period_end": end_date,
            "history": history_points,
            "trend": trend,
            "average_balance": average_balance
        }
    
    async def get_account_overview(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive financial overview from Plaid accounts.
        
        Args:
            user_id: User identifier
            
        Returns:
            Financial overview with net worth and cash flow
        """
        logger.info(f"Getting account overview for user {user_id}")
        
        accounts_data = await self.list_user_accounts(user_id)
        accounts = accounts_data["accounts"]
        
        if not accounts:
            raise NotFoundError("No Plaid accounts found for user")
        
        # Calculate totals from Plaid data
        total_assets = Decimal("0")
        total_liabilities = Decimal("0")
        
        for account in accounts:
            balance = account.balances.get("current", Decimal("0"))
            
            if account.type == "credit":
                # Credit accounts are liabilities
                total_liabilities += abs(balance)
            else:
                # Other accounts are assets
                total_assets += balance
        
        net_worth = total_assets - total_liabilities
        
        # Calculate monthly cash flow from Plaid transactions
        monthly_income, monthly_expenses = await self._calculate_monthly_cash_flow_from_plaid(user_id)
        
        # Determine cash flow trend
        cash_flow = monthly_income - monthly_expenses
        if cash_flow > Decimal("500"):
            cash_flow_trend = "positive"
        elif cash_flow < Decimal("-500"):
            cash_flow_trend = "negative"
        else:
            cash_flow_trend = "neutral"
        
        return {
            "accounts": accounts,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "net_worth": net_worth,
            "monthly_income": monthly_income,
            "monthly_expenses": monthly_expenses,
            "cash_flow_trend": cash_flow_trend
        }
    
    # Private helper methods
    async def _generate_balance_history_from_plaid(
        self, 
        account_id: str,
        user_id: str,
        start_date: date, 
        end_date: date, 
        granularity: str
    ) -> List[BalanceHistoryPoint]:
        """Generate balance history from Plaid transaction data."""
        points = []
        
        # Get current balance
        account = await self.get_account_details(account_id, user_id)
        current_balance = account.balances.get("current", Decimal("0"))
        
        # Get all transactions in period
        plaid_accounts = await self.plaid_service.get_user_accounts(user_id)
        plaid_account = next((acc for acc in plaid_accounts if acc.account_id == account_id), None)
        
        if plaid_account:
            connection = await self.repo.get_plaid_connection(plaid_account.connection_id)
            transactions = await self.repo.get_plaid_transactions_by_date_range(
                connection.connection_id,
                start_date,
                end_date
            )
            
            # Filter for this account
            account_transactions = [t for t in transactions if t.account_id == account_id]
            
            # Calculate balance at each point by working backwards from current
            current_date = end_date
            balance = current_balance
            
            while current_date >= start_date:
                # Calculate balance at this date
                future_transactions = [t for t in account_transactions if t.date > current_date]
                adjustment = sum(-t.amount for t in future_transactions)  # Flip Plaid sign convention
                point_balance = current_balance - adjustment
                
                # Calculate change from previous point
                change = Decimal("0")
                if points:
                    change = point_balance - points[-1].balance
                
                points.insert(0, BalanceHistoryPoint(
                    date=current_date,
                    balance=point_balance,
                    change=change
                ))
                
                # Move to previous date based on granularity
                if granularity == "daily":
                    current_date -= timedelta(days=1)
                elif granularity == "weekly":
                    current_date -= timedelta(weeks=1)
                else:  # monthly
                    current_date -= timedelta(days=30)
        
        return points
    
    async def _calculate_monthly_cash_flow_from_plaid(self, user_id: str) -> tuple:
        """Calculate average monthly income and expenses from Plaid transactions."""
        # Get last 30 days of transactions
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        plaid_accounts = await self.plaid_service.get_user_accounts(user_id)
        
        total_income = Decimal("0")
        total_expenses = Decimal("0")
        
        for account in plaid_accounts:
            connection = await self.repo.get_plaid_connection(account.connection_id)
            transactions = await self.repo.get_plaid_transactions_by_date_range(
                connection.connection_id,
                start_date,
                end_date
            )
            
            account_transactions = [t for t in transactions if t.account_id == account.account_id]
            
            for transaction in account_transactions:
                if transaction.amount < 0:  # Plaid: negative = income/credit
                    total_income += abs(transaction.amount)
                else:  # Plaid: positive = expense/debit
                    total_expenses += transaction.amount
        
        return total_income, total_expenses
    
    def _calculate_statement_summary(self, transactions: List[StatementTransaction]) -> Dict[str, Decimal]:
        """Calculate statement summary by category."""
        summary = {}
        for transaction in transactions:
            category = transaction.category.value
            amount = abs(transaction.amount)
            summary[category] = summary.get(category, Decimal("0")) + amount
        return summary


# Dependency provider
def get_account_service() -> AccountService:
    """Dependency provider for account service."""
    return AccountService()


