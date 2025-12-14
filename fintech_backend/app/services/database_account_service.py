"""
Database-integrated account management service for the fintech backend.
"""
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.orm import Session

from ..database import get_db
from ..database.models import (
    User, Account, Transaction, AccountTypeEnum, AccountStatusEnum,
    TransactionTypeEnum, TransactionStatusEnum, TransactionDirectionEnum
)
from ..repositories.database_repository import (
    UserRepository, AccountRepository, TransactionRepository
)
from ..models.flat_account import (
    AccountCreateRequest, AccountUpdateRequest, AccountTransferRequest
)
from ..core.exceptions import (
    ValidationException, AccountNotFoundException, BusinessRuleViolationException,
    InsufficientFundsException, FintechException
)
from ..config.logging import get_logger

logger = get_logger(__name__)


class DatabaseAccountService:
    """Database-integrated service for managing financial accounts."""
    
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.account_repo = AccountRepository(db)
        self.transaction_repo = TransactionRepository(db)
    
    def list_user_accounts(self, user_id: str) -> Dict[str, Any]:
        """List all accounts for a user."""
        logger.info(f"Listing accounts for user {user_id}")
        
        # Validate user exists
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            raise AccountNotFoundException(f"User {user_id} not found")
        
        # Get all user accounts
        accounts = self.account_repo.get_accounts_by_user_id(user_id)
        
        # Find primary account
        primary_account_id = None
        for account in accounts:
            if account.is_primary:
                primary_account_id = account.id
                break
        
        logger.info(f"Found {len(accounts)} accounts for user {user_id}")
        return {
            "accounts": accounts,
            "total_count": len(accounts),
            "primary_account_id": primary_account_id
        }
    
    def get_account_details(self, account_id: str, user_id: str) -> Account:
        """Get detailed information for a specific account."""
        logger.info(f"Getting account details for {account_id}")
        
        account = self.account_repo.get_account_by_id(account_id)
        if not account:
            raise AccountNotFoundException(f"Account {account_id} not found")
        
        # Verify ownership
        if account.user_id != user_id:
            raise FintechException("You don't have access to this account", "UNAUTHORIZED", 403)
        
        return account
    
    def create_account(self, user_id: str, request: AccountCreateRequest) -> Dict[str, Any]:
        """Create a new financial account."""
        logger.info(f"Creating new account for user {user_id}")
        
        # Validate user exists
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            raise AccountNotFoundException(f"User {user_id} not found")
        
        # Check if user already has maximum accounts
        existing_accounts = self.account_repo.get_accounts_by_user_id(user_id)
        if len(existing_accounts) >= 5:  # Business rule: max 5 accounts per user
            raise BusinessRuleViolationException("MAX_ACCOUNTS", "Maximum number of accounts reached (5)")
        
        # Generate account number
        account_number = self._generate_account_number()
        
        # Determine if this should be primary account
        is_primary = len(existing_accounts) == 0  # First account is primary
        
        # Create account
        account = self.account_repo.create_account(
            user_id=user_id,
            account_name=request.account_name,
            account_type=AccountTypeEnum(request.account_type.value),
            account_number=account_number,
            currency=request.currency.value if hasattr(request.currency, 'value') else str(request.currency)
        )
        
        # Set as primary if needed
        if is_primary:
            self.account_repo.set_primary_account(user_id, account.id)
        
        # Process initial deposit if provided
        if hasattr(request, 'initial_deposit') and request.initial_deposit and request.initial_deposit > 0:
            self._process_initial_deposit(account, request.initial_deposit)
        
        # Calculate welcome bonus
        welcome_bonus = self._calculate_welcome_bonus(request.account_type, 
                                                    getattr(request, 'initial_deposit', Decimal('0')))
        if welcome_bonus > 0:
            self._apply_welcome_bonus(account, welcome_bonus)
        
        next_steps = self._generate_next_steps(request.account_type)
        
        logger.info(f"Account {account.id} created successfully for user {user_id}")
        return {
            "account": account,
            "welcome_bonus": welcome_bonus,
            "next_steps": next_steps
        }
    
    def update_account_settings(self, account_id: str, user_id: str, 
                              request: AccountUpdateRequest) -> Account:
        """Update account settings and preferences."""
        logger.info(f"Updating account settings for {account_id}")
        
        account = self.get_account_details(account_id, user_id)
        
        # Check if account can be updated
        if account.status in [AccountStatusEnum.CLOSED, AccountStatusEnum.SUSPENDED]:
            raise BusinessRuleViolationException("ACCOUNT_STATUS", "Cannot update closed or suspended account")
        
        # Update fields
        update_data = {}
        if request.account_name is not None:
            update_data['account_name'] = request.account_name
        
        if request.is_overdraft_enabled is not None:
            update_data['is_overdraft_enabled'] = request.is_overdraft_enabled
            if request.is_overdraft_enabled:
                update_data['overdraft_limit'] = 1000.00
            else:
                update_data['overdraft_limit'] = 0.00
        
        if request.minimum_balance is not None:
            if request.minimum_balance > account.current_balance:
                raise BusinessRuleViolationException("MINIMUM_BALANCE", "Cannot set minimum balance above current balance")
            update_data['minimum_balance'] = request.minimum_balance
        
        if request.is_primary is not None and request.is_primary:
            self.account_repo.set_primary_account(user_id, account_id)
        
        # Apply updates
        if update_data:
            for key, value in update_data.items():
                setattr(account, key, value)
            self.db.commit()
            self.db.refresh(account)
        
        logger.info(f"Account {account_id} settings updated successfully")
        return account
    
    def get_account_balance(self, account_id: str, user_id: str) -> Dict[str, Any]:
        """Get current account balance information."""
        logger.info(f"Getting balance for account {account_id}")
        
        account = self.get_account_details(account_id, user_id)
        
        return {
            "account_id": account_id,
            "current_balance": account.current_balance,
            "available_balance": account.available_balance,
            "pending_balance": account.pending_balance,
            "currency": account.currency,
            "last_updated": account.updated_at
        }
    
    def transfer_between_accounts(self, user_id: str, 
                                request: AccountTransferRequest) -> Dict[str, Any]:
        """Transfer money between user's accounts."""
        logger.info(f"Processing transfer from {request.from_account_id} to {request.to_account_id}")
        
        # Get and validate both accounts
        from_account = self.get_account_details(request.from_account_id, user_id)
        to_account = self.get_account_details(request.to_account_id, user_id)
        
        # Validate accounts are active
        if from_account.status != AccountStatusEnum.ACTIVE:
            raise BusinessRuleViolationException("ACCOUNT_STATUS", "Source account is not active")
        if to_account.status != AccountStatusEnum.ACTIVE:
            raise BusinessRuleViolationException("ACCOUNT_STATUS", "Destination account is not active")
        
        # Check sufficient funds
        if from_account.available_balance < request.amount:
            raise InsufficientFundsException(from_account.available_balance, request.amount)
        
        # Check minimum balance requirement
        remaining_balance = from_account.available_balance - request.amount
        if remaining_balance < from_account.minimum_balance:
            raise InsufficientFundsException(from_account.available_balance, request.amount)
        
        # Process transfer
        try:
            # Update balances
            self.account_repo.update_balance(
                from_account.id,
                float(from_account.current_balance - request.amount),
                float(from_account.available_balance - request.amount)
            )
            
            self.account_repo.update_balance(
                to_account.id,
                float(to_account.current_balance + request.amount),
                float(to_account.available_balance + request.amount)
            )
            
            # Create transaction records
            # Debit transaction for source account
            self.transaction_repo.create_transaction(
                user_id=user_id,
                account_id=from_account.id,
                transaction_type=TransactionTypeEnum.TRANSFER_OUT,
                amount=float(-request.amount),  # Negative for debit
                currency=request.currency.value if hasattr(request.currency, 'value') else str(request.currency),
                description=f"Transfer to account {to_account.account_number}",
                status=TransactionStatusEnum.COMPLETED,
                direction=TransactionDirectionEnum.OUTBOUND
            )
            
            # Credit transaction for destination account
            self.transaction_repo.create_transaction(
                user_id=user_id,
                account_id=to_account.id,
                transaction_type=TransactionTypeEnum.TRANSFER_IN,
                amount=float(request.amount),  # Positive for credit
                currency=request.currency.value if hasattr(request.currency, 'value') else str(request.currency),
                description=f"Transfer from account {from_account.account_number}",
                status=TransactionStatusEnum.COMPLETED,
                direction=TransactionDirectionEnum.INBOUND
            )
            
            logger.info(f"Transfer completed successfully between accounts")
            return {
                "from_account": request.from_account_id,
                "to_account": request.to_account_id,
                "amount": request.amount,
                "currency": request.currency,
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "fee": Decimal("0.00")  # No fee for internal transfers
            }
            
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            raise BusinessRuleViolationException("TRANSFER_FAILED", f"Transfer failed: {str(e)}")
    
    def get_account_transactions(self, account_id: str, user_id: str, 
                               limit: int = 50, offset: int = 0) -> List[Transaction]:
        """Get transactions for an account."""
        logger.info(f"Getting transactions for account {account_id}")
        
        # Verify account ownership
        account = self.get_account_details(account_id, user_id)
        
        # Get transactions
        transactions = self.transaction_repo.get_transactions_by_account(
            account_id, limit, offset
        )
        
        return transactions
    
    def get_account_overview(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive financial overview for user."""
        logger.info(f"Getting account overview for user {user_id}")
        
        # Get all user accounts
        accounts_data = self.list_user_accounts(user_id)
        accounts = accounts_data["accounts"]
        
        if not accounts:
            raise AccountNotFoundException("No accounts found for user")
        
        # Calculate totals
        total_assets = Decimal("0")
        total_liabilities = Decimal("0")
        
        for account in accounts:
            balance = Decimal(str(account.current_balance))
            
            if account.account_type == AccountTypeEnum.CREDIT:
                # Credit accounts are liabilities
                total_liabilities += abs(balance)
            else:
                # Other accounts are assets
                total_assets += balance
        
        net_worth = total_assets - total_liabilities
        
        return {
            "accounts": accounts,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "net_worth": net_worth,
            "account_count": len(accounts)
        }
    
    # Private helper methods
    def _generate_account_number(self) -> str:
        """Generate a unique account number."""
        import random
        return f"ACC{random.randint(100000, 999999)}"
    
    def _process_initial_deposit(self, account: Account, amount: Decimal) -> None:
        """Process initial deposit for new account."""
        # Update account balance
        self.account_repo.update_balance(
            account.id,
            float(amount),
            float(amount)
        )
        
        # Create deposit transaction
        self.transaction_repo.create_transaction(
            user_id=account.user_id,
            account_id=account.id,
            transaction_type=TransactionTypeEnum.DEPOSIT,
            amount=float(amount),
            currency=account.currency,
            description="Initial deposit",
            status=TransactionStatusEnum.COMPLETED,
            direction=TransactionDirectionEnum.INBOUND
        )
        
        logger.info(f"Processed initial deposit of {amount} for account {account.id}")
    
    def _calculate_welcome_bonus(self, account_type, initial_deposit: Decimal) -> Decimal:
        """Calculate welcome bonus based on account type and deposit."""
        if hasattr(account_type, 'value'):
            account_type_str = account_type.value
        else:
            account_type_str = str(account_type)
            
        if account_type_str == "savings" and initial_deposit >= Decimal("1000"):
            return Decimal("50.00")  # $50 bonus for savings with $1000+ deposit
        elif account_type_str == "checking" and initial_deposit >= Decimal("500"):
            return Decimal("25.00")  # $25 bonus for checking with $500+ deposit
        return Decimal("0.00")
    
    def _apply_welcome_bonus(self, account: Account, bonus_amount: Decimal) -> None:
        """Apply welcome bonus to account."""
        # Update account balance
        new_current = float(account.current_balance + bonus_amount)
        new_available = float(account.available_balance + bonus_amount)
        
        self.account_repo.update_balance(account.id, new_current, new_available)
        
        # Create bonus transaction
        self.transaction_repo.create_transaction(
            user_id=account.user_id,
            account_id=account.id,
            transaction_type=TransactionTypeEnum.DEPOSIT,
            amount=float(bonus_amount),
            currency=account.currency,
            description="Welcome bonus",
            status=TransactionStatusEnum.COMPLETED,
            direction=TransactionDirectionEnum.INBOUND
        )
        
        logger.info(f"Applied welcome bonus of {bonus_amount} to account {account.id}")
    
    def _generate_next_steps(self, account_type) -> List[str]:
        """Generate recommended next steps for new account."""
        common_steps = [
            "Set up direct deposit",
            "Order a debit card",
            "Download mobile app"
        ]
        
        if hasattr(account_type, 'value'):
            account_type_str = account_type.value
        else:
            account_type_str = str(account_type)
        
        type_specific = {
            "savings": ["Set up automatic savings transfers", "Review interest rates"],
            "investment": ["Complete investment profile", "Fund your account"],
            "credit": ["Set up autopay", "Review credit terms"],
            "business": ["Add authorized users", "Set up business payments"]
        }
        
        return common_steps + type_specific.get(account_type_str, [])


# Dependency provider
def get_database_account_service(db: Session = None) -> DatabaseAccountService:
    """Dependency provider for database account service."""
    if db is None:
        db = next(get_db())
    return DatabaseAccountService(db)
