"""
Account management service for the fintech backend.
"""

import uuid
import random
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import asyncio

from app.models.account import (
    Account, AccountType, AccountStatus, CurrencyCode, AccountBalance,
    AccountStatement, StatementTransaction, TransactionCategory,
    AccountCreateRequest, AccountUpdateRequest, AccountTransferRequest,
    StatementRequest, BalanceHistoryRequest, BalanceHistoryPoint
)
from app.core.exceptions import (
    ValidationError, NotFoundError, BusinessLogicError,
    InsufficientFundsError, UnauthorizedError
)
from app.data.repository import get_repository_manager
from app.utils.validation import validate_user_exists, validate_currency_amount
from app.utils.calculations import calculate_fee, calculate_interest
from app.external.bank_api import get_bank_api_client
from app.config.logging import get_logger

logger = get_logger(__name__)


class AccountService:
    """Service for managing financial accounts and related operations."""
    
    def __init__(self):
        self.repo = get_repository_manager()
        self.bank_api = get_bank_api_client()
    
    async def list_user_accounts(
        self, 
        user_id: str,
        account_type: Optional[AccountType] = None,
        status: Optional[AccountStatus] = None
    ) -> Dict[str, Any]:
        """
        List all accounts for a user with optional filtering.
        
        Args:
            user_id: User identifier
            account_type: Optional account type filter
            status: Optional status filter
            
        Returns:
            Dictionary with accounts list and metadata
        """
        logger.info(f"Listing accounts for user {user_id}")
        
        # Validate user exists
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        
        # Get all user accounts
        all_accounts = await self.repo.get_user_accounts(user_id)
        
        # Apply filters
        filtered_accounts = []
        primary_account_id = None
        
        for account in all_accounts:
            if account_type and account.account_type != account_type:
                continue
            if status and account.status != status:
                continue
                
            filtered_accounts.append(account)
            
            if account.is_primary:
                primary_account_id = account.account_id
        
        logger.info(f"Found {len(filtered_accounts)} accounts for user {user_id}")
        return {
            "accounts": filtered_accounts,
            "total_count": len(filtered_accounts),
            "primary_account_id": primary_account_id
        }
    
    async def get_account_details(self, account_id: str, user_id: str) -> Account:
        """
        Get detailed information for a specific account.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            
        Returns:
            Account details
        """
        logger.info(f"Getting account details for {account_id}")
        
        account = await self.repo.get_account_by_id(account_id)
        if not account:
            raise NotFoundError(f"Account {account_id} not found")
        
        # Verify ownership
        if account.user_id != user_id:
            raise UnauthorizedError("You don't have access to this account")
        
        # Update balance from external source
        await self._refresh_account_balance(account)
        
        return account
    
    async def create_account(
        self, 
        user_id: str, 
        request: AccountCreateRequest
    ) -> Dict[str, Any]:
        """
        Create a new financial account.
        
        Args:
            user_id: User identifier
            request: Account creation request
            
        Returns:
            Created account and welcome information
        """
        logger.info(f"Creating new account for user {user_id}")
        
        # Validate user exists
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        
        # Check if user already has maximum accounts
        existing_accounts = await self.repo.get_user_accounts(user_id)
        if len(existing_accounts) >= 5:  # Business rule: max 5 accounts per user
            raise BusinessLogicError("Maximum number of accounts reached (5)")
        
        # Validate initial deposit if provided
        if request.initial_deposit and request.initial_deposit < request.minimum_balance:
            raise ValidationError("Initial deposit must be at least the minimum balance")
        
        # Generate account details
        account_id = str(uuid.uuid4())
        account_number = self._generate_account_number()
        
        # Create account balance
        initial_balance = request.initial_deposit or Decimal("0")
        balance = AccountBalance(
            currency=request.currency,
            available_balance=initial_balance,
            current_balance=initial_balance,
            pending_balance=Decimal("0"),
            overdraft_limit=Decimal("1000") if request.is_overdraft_enabled else None,
            reserved_balance=Decimal("0")
        )
        
        # Determine if this should be primary account
        is_primary = len(existing_accounts) == 0  # First account is primary
        
        # Set interest rate for savings accounts
        interest_rate = None
        if request.account_type == AccountType.SAVINGS:
            interest_rate = Decimal("2.5")  # 2.5% annual rate
        elif request.account_type == AccountType.CHECKING:
            interest_rate = Decimal("0.1")  # 0.1% annual rate
        
        # Create account
        account = Account(
            account_id=account_id,
            user_id=user_id,
            account_type=request.account_type,
            account_name=request.account_name,
            account_number=account_number,
            status=AccountStatus.ACTIVE,
            balance=balance,
            is_primary=is_primary,
            is_overdraft_enabled=request.is_overdraft_enabled,
            minimum_balance=request.minimum_balance,
            interest_rate=interest_rate,
            monthly_fee=self._calculate_monthly_fee(request.account_type),
            opening_date=date.today(),
            routing_number="123456789",  # Mock routing number
            swift_code="FINTECH01",  # Mock SWIFT code
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Save account
        await self.repo.create_account(account)
        
        # Process initial deposit if provided
        if request.initial_deposit and request.initial_deposit > 0:
            await self._process_initial_deposit(account, request.initial_deposit)
        
        # Calculate welcome bonus
        welcome_bonus = self._calculate_welcome_bonus(request.account_type, initial_balance)
        if welcome_bonus > 0:
            await self._apply_welcome_bonus(account, welcome_bonus)
        
        next_steps = self._generate_next_steps(request.account_type)
        
        logger.info(f"Account {account_id} created successfully for user {user_id}")
        return {
            "account": account,
            "welcome_bonus": welcome_bonus,
            "next_steps": next_steps
        }
    
    async def update_account_settings(
        self, 
        account_id: str, 
        user_id: str, 
        request: AccountUpdateRequest
    ) -> Account:
        """
        Update account settings and preferences.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            request: Update request
            
        Returns:
            Updated account
        """
        logger.info(f"Updating account settings for {account_id}")
        
        account = await self.get_account_details(account_id, user_id)
        
        # Check if account can be updated
        if account.status in [AccountStatus.CLOSED, AccountStatus.SUSPENDED]:
            raise BusinessLogicError("Cannot update closed or suspended account")
        
        # Update fields
        if request.account_name is not None:
            account.account_name = request.account_name
        
        if request.is_overdraft_enabled is not None:
            account.is_overdraft_enabled = request.is_overdraft_enabled
            # Update overdraft limit
            if request.is_overdraft_enabled:
                account.balance.overdraft_limit = Decimal("1000")
            else:
                account.balance.overdraft_limit = None
        
        if request.minimum_balance is not None:
            if request.minimum_balance > account.balance.current_balance:
                raise BusinessLogicError("Cannot set minimum balance above current balance")
            account.minimum_balance = request.minimum_balance
        
        if request.is_primary is not None and request.is_primary:
            # Unset other primary accounts first
            await self._unset_primary_accounts(user_id)
            account.is_primary = True
        
        account.updated_at = datetime.utcnow()
        await self.repo.update_account(account)
        
        logger.info(f"Account {account_id} settings updated successfully")
        return account
    
    async def get_account_balance(self, account_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get current account balance information.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            
        Returns:
            Current balance information
        """
        logger.info(f"Getting balance for account {account_id}")
        
        account = await self.get_account_details(account_id, user_id)
        
        return {
            "account_id": account_id,
            "balance": account.balance,
            "last_updated": account.updated_at
        }
    
    async def generate_statement(
        self, 
        account_id: str, 
        user_id: str, 
        request: StatementRequest
    ) -> Dict[str, Any]:
        """
        Generate account statement for specified period.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            request: Statement generation request
            
        Returns:
            Generated statement with transactions
        """
        logger.info(f"Generating statement for account {account_id}")
        
        account = await self.get_account_details(account_id, user_id)
        
        # Validate date range
        if request.end_date > date.today():
            raise ValidationError("End date cannot be in the future")
        
        # Get transactions for the period
        start_datetime = datetime.combine(request.start_date, datetime.min.time())
        end_datetime = datetime.combine(request.end_date, datetime.max.time())
        
        transactions = await self.repo.get_account_transactions(
            account_id, start_datetime, end_datetime
        )
        
        # Calculate statement summary
        total_credits = sum(t.amount for t in transactions if t.amount > 0)
        total_debits = abs(sum(t.amount for t in transactions if t.amount < 0))
        
        # Get opening balance (balance at start of period)
        opening_balance = await self._get_balance_at_date(account_id, request.start_date)
        closing_balance = opening_balance + total_credits - total_debits
        
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
            transaction_count=len(transactions),
            generated_at=datetime.utcnow()
        )
        
        # Convert transactions to statement format
        statement_transactions = []
        running_balance = opening_balance
        
        for transaction in sorted(transactions, key=lambda x: x.created_at):
            running_balance += transaction.amount
            
            statement_transactions.append(StatementTransaction(
                transaction_id=transaction.transaction_id,
                date=transaction.created_at.date(),
                description=transaction.description,
                category=TransactionCategory.OTHER,  # Would be determined by transaction type
                amount=transaction.amount,
                balance_after=running_balance,
                reference_number=getattr(transaction, 'reference_number', None)
            ))
        
        # Calculate summary by category
        summary = self._calculate_statement_summary(statement_transactions)
        
        logger.info(f"Statement generated for account {account_id}: {len(statement_transactions)} transactions")
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
        Get account balance history over time.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            request: Balance history request
            
        Returns:
            Balance history data and trend analysis
        """
        logger.info(f"Getting balance history for account {account_id}")
        
        account = await self.get_account_details(account_id, user_id)
        
        # Calculate period
        end_date = date.today()
        start_date = end_date - timedelta(days=request.days)
        
        # Generate balance history points
        history_points = await self._generate_balance_history(
            account_id, start_date, end_date, request.granularity
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
    
    async def transfer_between_accounts(
        self, 
        user_id: str, 
        request: AccountTransferRequest
    ) -> Dict[str, Any]:
        """
        Transfer money between user's accounts.
        
        Args:
            user_id: User identifier
            request: Transfer request
            
        Returns:
            Transfer confirmation details
        """
        logger.info(f"Processing transfer from {request.from_account_id} to {request.to_account_id}")
        
        # Get and validate both accounts
        from_account = await self.get_account_details(request.from_account_id, user_id)
        to_account = await self.get_account_details(request.to_account_id, user_id)
        
        # Validate accounts are active
        if from_account.status != AccountStatus.ACTIVE:
            raise BusinessLogicError("Source account is not active")
        if to_account.status != AccountStatus.ACTIVE:
            raise BusinessLogicError("Destination account is not active")
        
        # Validate currency compatibility
        if from_account.balance.currency != request.currency:
            raise ValidationError("Transfer currency does not match source account currency")
        
        # Calculate transfer fee
        transfer_fee = calculate_fee(request.amount, "internal_transfer")
        total_amount = request.amount + transfer_fee
        
        # Check sufficient funds
        if from_account.balance.available_balance < total_amount:
            raise InsufficientFundsError("Insufficient funds for transfer")
        
        # Check minimum balance requirement
        remaining_balance = from_account.balance.available_balance - total_amount
        if remaining_balance < from_account.minimum_balance:
            raise InsufficientFundsError("Transfer would violate minimum balance requirement")
        
        # Process transfer
        transfer_id = str(uuid.uuid4())
        
        # Update balances
        from_account.balance.available_balance -= total_amount
        from_account.balance.current_balance -= total_amount
        from_account.updated_at = datetime.utcnow()
        
        # Handle currency conversion if needed
        converted_amount = await self._convert_currency(
            request.amount, request.currency, to_account.balance.currency
        )
        
        to_account.balance.available_balance += converted_amount
        to_account.balance.current_balance += converted_amount
        to_account.updated_at = datetime.utcnow()
        
        # Save updated accounts
        await self.repo.update_account(from_account)
        await self.repo.update_account(to_account)
        
        # Create transfer transaction records
        await self._create_transfer_transactions(
            transfer_id, from_account, to_account, request, transfer_fee
        )
        
        logger.info(f"Transfer {transfer_id} completed successfully")
        return {
            "transfer_id": transfer_id,
            "from_account": request.from_account_id,
            "to_account": request.to_account_id,
            "amount": request.amount,
            "currency": request.currency,
            "status": "completed",
            "completed_at": datetime.utcnow(),
            "fee": transfer_fee
        }
    
    async def get_account_overview(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive financial overview for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Financial overview with net worth and cash flow
        """
        logger.info(f"Getting account overview for user {user_id}")
        
        # Get all user accounts
        accounts_data = await self.list_user_accounts(user_id)
        accounts = accounts_data["accounts"]
        
        if not accounts:
            raise NotFoundError("No accounts found for user")
        
        # Calculate totals
        total_assets = Decimal("0")
        total_liabilities = Decimal("0")
        
        for account in accounts:
            balance = account.balance.current_balance
            
            if account.account_type == AccountType.CREDIT:
                # Credit accounts are liabilities
                total_liabilities += abs(balance)
            else:
                # Other accounts are assets
                total_assets += balance
        
        net_worth = total_assets - total_liabilities
        
        # Calculate monthly cash flow (mock data)
        monthly_income, monthly_expenses = await self._calculate_monthly_cash_flow(user_id)
        
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
    
    async def close_account(self, account_id: str, user_id: str, reason: str = "User requested") -> Account:
        """
        Close an account permanently.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            reason: Reason for closure
            
        Returns:
            Closed account
        """
        logger.info(f"Closing account {account_id}")
        
        account = await self.get_account_details(account_id, user_id)
        
        # Validate account can be closed
        if account.status == AccountStatus.CLOSED:
            raise BusinessLogicError("Account is already closed")
        
        if account.balance.current_balance != 0:
            raise BusinessLogicError("Cannot close account with non-zero balance")
        
        if account.is_primary:
            # Check if user has other accounts to make primary
            other_accounts = await self.repo.get_user_accounts(user_id)
            active_accounts = [acc for acc in other_accounts if acc.account_id != account_id and acc.status == AccountStatus.ACTIVE]
            
            if active_accounts:
                # Make the first active account primary
                active_accounts[0].is_primary = True
                await self.repo.update_account(active_accounts[0])
                logger.info(f"Made account {active_accounts[0].account_id} primary")
        
        # Close account
        account.status = AccountStatus.CLOSED
        account.is_primary = False
        account.updated_at = datetime.utcnow()
        
        await self.repo.update_account(account)
        
        logger.info(f"Account {account_id} closed successfully")
        return account
    
    # Private helper methods
    async def _refresh_account_balance(self, account: Account) -> None:
        """Refresh account balance from external source."""
        try:
            # Simulate external balance check
            external_balance = await self.bank_api.get_account_balance(account.account_number)
            if external_balance and 'balance' in external_balance:
                # Update balance if different
                new_balance = Decimal(str(external_balance['balance']))
                if abs(new_balance - account.balance.current_balance) > Decimal("0.01"):
                    account.balance.current_balance = new_balance
                    account.balance.available_balance = new_balance - account.balance.reserved_balance
                    account.updated_at = datetime.utcnow()
                    await self.repo.update_account(account)
        except Exception as e:
            logger.warning(f"Failed to refresh balance for account {account.account_id}: {e}")
    
    def _generate_account_number(self) -> str:
        """Generate a masked account number."""
        return f"****{random.randint(1000, 9999)}"
    
    def _calculate_monthly_fee(self, account_type: AccountType) -> Decimal:
        """Calculate monthly fee based on account type."""
        fees = {
            AccountType.CHECKING: Decimal("5.00"),
            AccountType.SAVINGS: Decimal("0.00"),
            AccountType.INVESTMENT: Decimal("10.00"),
            AccountType.CREDIT: Decimal("0.00"),
            AccountType.BUSINESS: Decimal("15.00")
        }
        return fees.get(account_type, Decimal("0.00"))
    
    async def _process_initial_deposit(self, account: Account, amount: Decimal) -> None:
        """Process initial deposit for new account."""
        # Create deposit transaction
        transaction_id = str(uuid.uuid4())
        # This would typically create a transaction record
        logger.info(f"Processed initial deposit of {amount} for account {account.account_id}")
    
    def _calculate_welcome_bonus(self, account_type: AccountType, initial_deposit: Decimal) -> Decimal:
        """Calculate welcome bonus based on account type and deposit."""
        if account_type == AccountType.SAVINGS and initial_deposit >= Decimal("1000"):
            return Decimal("50.00")  # $50 bonus for savings with $1000+ deposit
        elif account_type == AccountType.CHECKING and initial_deposit >= Decimal("500"):
            return Decimal("25.00")  # $25 bonus for checking with $500+ deposit
        return Decimal("0.00")
    
    async def _apply_welcome_bonus(self, account: Account, bonus_amount: Decimal) -> None:
        """Apply welcome bonus to account."""
        account.balance.available_balance += bonus_amount
        account.balance.current_balance += bonus_amount
        await self.repo.update_account(account)
        logger.info(f"Applied welcome bonus of {bonus_amount} to account {account.account_id}")
    
    def _generate_next_steps(self, account_type: AccountType) -> List[str]:
        """Generate recommended next steps for new account."""
        common_steps = [
            "Set up direct deposit",
            "Order a debit card",
            "Download mobile app"
        ]
        
        type_specific = {
            AccountType.SAVINGS: ["Set up automatic savings transfers", "Review interest rates"],
            AccountType.INVESTMENT: ["Complete investment profile", "Fund your account"],
            AccountType.CREDIT: ["Set up autopay", "Review credit terms"],
            AccountType.BUSINESS: ["Add authorized users", "Set up business payments"]
        }
        
        return common_steps + type_specific.get(account_type, [])
    
    async def _unset_primary_accounts(self, user_id: str) -> None:
        """Remove primary flag from all user accounts."""
        accounts = await self.repo.get_user_accounts(user_id)
        for account in accounts:
            if account.is_primary:
                account.is_primary = False
                await self.repo.update_account(account)
    
    async def _get_balance_at_date(self, account_id: str, target_date: date) -> Decimal:
        """Get account balance at a specific date."""
        # In a real implementation, this would calculate based on transaction history
        # For mock, return current balance with some variation
        account = await self.repo.get_account_by_id(account_id)
        variation = Decimal(str(random.uniform(-100, 100)))
        return max(Decimal("0"), account.balance.current_balance + variation)
    
    async def _generate_balance_history(
        self, 
        account_id: str, 
        start_date: date, 
        end_date: date, 
        granularity: str
    ) -> List[BalanceHistoryPoint]:
        """Generate balance history points."""
        points = []
        current_date = start_date
        
        # Get current balance as reference
        account = await self.repo.get_account_by_id(account_id)
        current_balance = account.balance.current_balance
        
        # Generate historical points with realistic variation
        base_balance = current_balance
        
        while current_date <= end_date:
            # Add some random variation to balance
            variation = Decimal(str(random.uniform(-50, 50)))
            balance = max(Decimal("0"), base_balance + variation)
            
            # Calculate change from previous point
            change = Decimal("0")
            if points:
                change = balance - points[-1].balance
            
            points.append(BalanceHistoryPoint(
                date=current_date,
                balance=balance,
                change=change
            ))
            
            # Move to next date based on granularity
            if granularity == "daily":
                current_date += timedelta(days=1)
            elif granularity == "weekly":
                current_date += timedelta(weeks=1)
            else:  # monthly
                # Add approximately one month
                current_date += timedelta(days=30)
            
            # Slightly adjust base balance for next point
            base_balance += Decimal(str(random.uniform(-20, 20)))
            base_balance = max(Decimal("0"), base_balance)
        
        return points
    
    async def _convert_currency(
        self, 
        amount: Decimal, 
        from_currency: CurrencyCode, 
        to_currency: CurrencyCode
    ) -> Decimal:
        """Convert amount between currencies."""
        if from_currency == to_currency:
            return amount
        
        # Mock conversion rates (in a real app, would use external service)
        rates = {
            "USD_EUR": Decimal("0.85"),
            "USD_GBP": Decimal("0.75"),
            "EUR_USD": Decimal("1.18"),
            "GBP_USD": Decimal("1.33")
        }
        
        rate_key = f"{from_currency}_{to_currency}"
        rate = rates.get(rate_key, Decimal("1.0"))
        
        return amount * rate
    
    async def _create_transfer_transactions(
        self, 
        transfer_id: str, 
        from_account: Account, 
        to_account: Account, 
        request: AccountTransferRequest, 
        fee: Decimal
    ) -> None:
        """Create transaction records for transfer."""
        # This would create transaction records in the database
        # For now, just log the operation
        logger.info(f"Created transfer transactions for {transfer_id}")
    
    def _calculate_statement_summary(self, transactions: List[StatementTransaction]) -> Dict[str, Decimal]:
        """Calculate statement summary by category."""
        summary = {}
        for transaction in transactions:
            category = transaction.category.value
            amount = abs(transaction.amount)
            summary[category] = summary.get(category, Decimal("0")) + amount
        return summary
    
    async def _calculate_monthly_cash_flow(self, user_id: str) -> tuple:
        """Calculate average monthly income and expenses."""
        # Mock calculation - in real app would analyze transaction history
        monthly_income = Decimal(str(random.uniform(3000, 8000)))
        monthly_expenses = Decimal(str(random.uniform(2000, 6000)))
        return monthly_income, monthly_expenses


# Dependency provider
def get_account_service() -> AccountService:
    """Dependency provider for account service."""
    return AccountService()
