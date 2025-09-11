from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from app.database.config import get_db
from app.repositories.database_repository import TransactionRepository, AccountRepository
from app.models.transaction import TransactionResponse, TransactionCreateRequest, TransactionFilters
from app.database.models import Transaction as DBTransaction
from app.models.transaction import TransactionType, TransactionStatus
from app.core.exceptions import AccountNotFoundException, ValidationException
import uuid
from datetime import datetime
from decimal import Decimal

class DatabaseTransactionService:
    def __init__(self, db: Session):
        self.db = db
        self.transaction_repository = TransactionRepository(db)
        self.account_repository = AccountRepository(db)
    
    def get_user_transactions(self, user_id: str, filters: TransactionFilters, db: Session) -> List[TransactionResponse]:
        """Get transactions for a user with optional filters"""
        transactions = self.transaction_repository.get_transactions_by_user(
            user_id, filters.limit, filters.offset
        )
        
        # Apply additional filters
        filtered_transactions = []
        for transaction in transactions:
            # Filter by account if specified
            if filters.account_id and transaction.account_id != filters.account_id:
                continue
            
            # Filter by type if specified
            if filters.transaction_type and transaction.transaction_type.value != filters.transaction_type:
                continue
            
            # Filter by status if specified
            if filters.status and transaction.status.value != filters.status:
                continue
            
            # Filter by date range if specified
            if filters.start_date and transaction.created_at.date() < filters.start_date:
                continue
            if filters.end_date and transaction.created_at.date() > filters.end_date:
                continue
            
            # Filter by amount range if specified
            if filters.min_amount and transaction.amount < Decimal(str(filters.min_amount)):
                continue
            if filters.max_amount and transaction.amount > Decimal(str(filters.max_amount)):
                continue
            
            filtered_transactions.append(transaction)
        
        return [self._convert_to_response(transaction) for transaction in filtered_transactions]
    
    def get_transaction_by_id(self, transaction_id: str, user_id: str, db: Session) -> TransactionResponse:
        """Get a specific transaction by ID"""
        transaction = self.transaction_repository.get_transaction_by_id(transaction_id)
        if not transaction:
            raise AccountNotFoundException(f"Transaction with ID {transaction_id} not found")
        
        # Verify the transaction belongs to the user (through account)
        account = self.account_repository.get_account_by_id(transaction.account_id)
        if not account or account.user_id != user_id:
            raise AccountNotFoundException(f"Transaction with ID {transaction_id} not found")
        
        return self._convert_to_response(transaction)
    
    def create_transaction(self, user_id: str, transaction_data: TransactionCreateRequest, db: Session) -> TransactionResponse:
        """Create a new transaction"""
        # Verify the account exists and belongs to the user
        account = self.account_repository.get_account_by_id(transaction_data.account_id)
        if not account or account.user_id != user_id:
            raise ValidationException("Invalid account ID or account does not belong to user")
        
        # Check if account has sufficient balance for debit transactions
        if transaction_data.transaction_type in ['debit', 'withdrawal', 'transfer_out']:
            if account.balance < Decimal(str(transaction_data.amount)):
                raise ValidationException("Insufficient account balance")
        
        # Create transaction
        transaction_dict = {
            "id": str(uuid.uuid4()),
            "account_id": transaction_data.account_id,
            "transaction_type": TransactionType(transaction_data.transaction_type),
            "amount": Decimal(str(transaction_data.amount)),
            "currency": transaction_data.currency,
            "description": transaction_data.description,
            "reference": transaction_data.reference or f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}",
            "status": TransactionStatus.PENDING,
            "metadata": transaction_data.metadata or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        transaction = self.transaction_repository.create(db, transaction_dict)
        
        # Update account balance
        self._update_account_balance(account, transaction, db)
        
        # Mark transaction as completed
        updated_transaction = self.transaction_repository.update(db, transaction.id, {
            "status": TransactionStatus.COMPLETED,
            "updated_at": datetime.utcnow()
        })
        
        return self._convert_to_response(updated_transaction)
    
    def get_account_transactions(self, account_id: str, user_id: str, limit: int = 50, offset: int = 0, db: Session = None) -> List[TransactionResponse]:
        """Get transactions for a specific account"""
        # Verify account belongs to user
        account = self.account_repository.get_account_by_id(account_id)
        if not account or account.user_id != user_id:
            raise AccountNotFoundException(f"Account with ID {account_id} not found")
        
        transactions = self.transaction_repository.get_transactions_by_account(account_id, limit, offset)
        return [self._convert_to_response(transaction) for transaction in transactions]
    
    def get_transaction_summary(self, user_id: str, account_id: Optional[str] = None, db: Session = None) -> Dict[str, Any]:
        """Get transaction summary for user or specific account"""
        if account_id:
            # Verify account belongs to user
            account = self.account_repository.get_account_by_id(account_id)
            if not account or account.user_id != user_id:
                raise AccountNotFoundException(f"Account with ID {account_id} not found")
            transactions = self.transaction_repository.get_transactions_by_account(account_id)
        else:
            transactions = self.transaction_repository.get_transactions_by_user(user_id)
        
        # Calculate summary
        total_transactions = len(transactions)
        total_credits = sum(t.amount for t in transactions if t.transaction_type in [TransactionType.CREDIT, TransactionType.DEPOSIT])
        total_debits = sum(t.amount for t in transactions if t.transaction_type in [TransactionType.DEBIT, TransactionType.WITHDRAWAL])
        
        # Group by status
        status_counts = {}
        for transaction in transactions:
            status = transaction.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Group by type
        type_counts = {}
        for transaction in transactions:
            tx_type = transaction.transaction_type.value
            type_counts[tx_type] = type_counts.get(tx_type, 0) + 1
        
        return {
            "total_transactions": total_transactions,
            "total_credits": float(total_credits),
            "total_debits": float(total_debits),
            "net_amount": float(total_credits - total_debits),
            "status_breakdown": status_counts,
            "type_breakdown": type_counts
        }
    
    def _update_account_balance(self, account, transaction: DBTransaction, db: Session):
        """Update account balance based on transaction type"""
        amount = transaction.amount
        
        if transaction.transaction_type in [TransactionType.CREDIT, TransactionType.DEPOSIT]:
            new_balance = account.balance + amount
        elif transaction.transaction_type in [TransactionType.DEBIT, TransactionType.WITHDRAWAL]:
            new_balance = account.balance - amount
        else:
            # For other transaction types, don't modify balance
            return
        
        # Update account balance
        self.account_repository.update(db, account.id, {
            "balance": new_balance,
            "updated_at": datetime.utcnow()
        })
    
    def _convert_to_response(self, transaction: DBTransaction) -> TransactionResponse:
        """Convert database transaction to response model"""
        return TransactionResponse(
            id=transaction.id,
            account_id=transaction.account_id,
            transaction_type=transaction.transaction_type.value,
            amount=float(transaction.amount),
            currency=transaction.currency,
            description=transaction.description,
            reference=transaction.reference,
            status=transaction.status.value,
            metadata=transaction.metadata,
            created_at=transaction.created_at,
            updated_at=transaction.updated_at
        )
