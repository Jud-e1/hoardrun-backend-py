"""
Database repository implementations for data access.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from datetime import datetime, date

from ..database.models import (
    User, Account, Transaction, Card, Investment, P2PTransaction, Transfer,
    AccountTypeEnum, AccountStatusEnum, TransactionTypeEnum, TransactionStatusEnum,
    CardTypeEnum, CardStatusEnum
)
class UserRepository:
    """Repository for User operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_user(self, email: str, first_name: str, last_name: str, 
                   phone_number: Optional[str] = None) -> User:
        """Create a new user."""
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.db.query(User).filter(User.email == email).first()
    
    def update_user(self, user_id: str, **kwargs) -> Optional[User]:
        """Update user information."""
        user = self.get_user_by_id(user_id)
        if user:
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            self.db.commit()
            self.db.refresh(user)
        return user
    
    def delete_user(self, user_id: str) -> bool:
        """Delete user."""
        user = self.get_user_by_id(user_id)
        if user:
            self.db.delete(user)
            self.db.commit()
            return True
        return False


class AccountRepository:
    """Repository for Account operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_account(self, user_id: str, account_name: str, account_type: AccountTypeEnum,
                      account_number: str, currency: str = "USD") -> Account:
        """Create a new account."""
        account = Account(
            user_id=user_id,
            account_name=account_name,
            account_type=account_type,
            account_number=account_number,
            currency=currency
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account
    
    def get_account_by_id(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        return self.db.query(Account).filter(Account.id == account_id).first()
    
    def get_accounts_by_user_id(self, user_id: str) -> List[Account]:
        """Get all accounts for a user."""
        return self.db.query(Account).filter(Account.user_id == user_id).all()
    
    def get_account_by_number(self, account_number: str) -> Optional[Account]:
        """Get account by account number."""
        return self.db.query(Account).filter(Account.account_number == account_number).first()
    
    def update_balance(self, account_id: str, current_balance: float, 
                      available_balance: float) -> Optional[Account]:
        """Update account balance."""
        account = self.get_account_by_id(account_id)
        if account:
            account.current_balance = current_balance
            account.available_balance = available_balance
            self.db.commit()
            self.db.refresh(account)
        return account
    
    def set_primary_account(self, user_id: str, account_id: str) -> bool:
        """Set an account as primary for a user."""
        # First, unset all primary accounts for the user
        self.db.query(Account).filter(Account.user_id == user_id).update(
            {Account.is_primary: False}
        )
        
        # Set the specified account as primary
        account = self.get_account_by_id(account_id)
        if account and account.user_id == user_id:
            account.is_primary = True
            self.db.commit()
            return True
        return False


class TransactionRepository:
    """Repository for Transaction operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_transaction(self, user_id: str, account_id: str, 
                          transaction_type: TransactionTypeEnum,
                          amount: float, currency: str, description: str,
                          **kwargs) -> Transaction:
        """Create a new transaction."""
        transaction = Transaction(
            user_id=user_id,
            account_id=account_id,
            transaction_type=transaction_type,
            amount=amount,
            currency=currency,
            description=description,
            transaction_date=datetime.utcnow(),
            **kwargs
        )
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        return transaction
    
    def get_transaction_by_id(self, transaction_id: str) -> Optional[Transaction]:
        """Get transaction by ID."""
        return self.db.query(Transaction).filter(Transaction.id == transaction_id).first()
    
    def get_transactions_by_account(self, account_id: str, limit: int = 50, 
                                   offset: int = 0) -> List[Transaction]:
        """Get transactions for an account."""
        return (self.db.query(Transaction)
                .filter(Transaction.account_id == account_id)
                .order_by(desc(Transaction.transaction_date))
                .limit(limit)
                .offset(offset)
                .all())
    
    def get_transactions_by_user(self, user_id: str, limit: int = 50, 
                                offset: int = 0) -> List[Transaction]:
        """Get transactions for a user."""
        return (self.db.query(Transaction)
                .filter(Transaction.user_id == user_id)
                .order_by(desc(Transaction.transaction_date))
                .limit(limit)
                .offset(offset)
                .all())
    
    def get_transactions_by_date_range(self, account_id: str, start_date: date, 
                                      end_date: date) -> List[Transaction]:
        """Get transactions within a date range."""
        return (self.db.query(Transaction)
                .filter(
                    and_(
                        Transaction.account_id == account_id,
                        Transaction.transaction_date >= start_date,
                        Transaction.transaction_date <= end_date
                    )
                )
                .order_by(desc(Transaction.transaction_date))
                .all())
    
    def update_transaction_status(self, transaction_id: str, 
                                 status: TransactionStatusEnum) -> Optional[Transaction]:
        """Update transaction status."""
        transaction = self.get_transaction_by_id(transaction_id)
        if transaction:
            transaction.status = status
            if status == TransactionStatusEnum.COMPLETED:
                transaction.posted_date = datetime.utcnow()
            self.db.commit()
            self.db.refresh(transaction)
        return transaction


class CardRepository:
    """Repository for Card operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_card(self, user_id: str, account_id: str, card_type: CardTypeEnum,
                   cardholder_name: str, card_number_masked: str,
                   expiry_month: int, expiry_year: int) -> Card:
        """Create a new card."""
        card = Card(
            user_id=user_id,
            account_id=account_id,
            card_type=card_type,
            cardholder_name=cardholder_name,
            card_number_masked=card_number_masked,
            expiry_month=expiry_month,
            expiry_year=expiry_year
        )
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        return card
    
    def get_card_by_id(self, card_id: str) -> Optional[Card]:
        """Get card by ID."""
        return self.db.query(Card).filter(Card.id == card_id).first()
    
    def get_cards_by_user_id(self, user_id: str) -> List[Card]:
        """Get all cards for a user."""
        return self.db.query(Card).filter(Card.user_id == user_id).all()
    
    def get_cards_by_account_id(self, account_id: str) -> List[Card]:
        """Get all cards for an account."""
        return self.db.query(Card).filter(Card.account_id == account_id).all()
    
    def update_card_status(self, card_id: str, status: CardStatusEnum) -> Optional[Card]:
        """Update card status."""
        card = self.get_card_by_id(card_id)
        if card:
            card.status = status
            self.db.commit()
            self.db.refresh(card)
        return card
    
    def update_card_limits(self, card_id: str, daily_limit: Optional[float] = None,
                          monthly_limit: Optional[float] = None) -> Optional[Card]:
        """Update card limits."""
        card = self.get_card_by_id(card_id)
        if card:
            if daily_limit is not None:
                card.daily_limit = daily_limit
            if monthly_limit is not None:
                card.monthly_limit = monthly_limit
            self.db.commit()
            self.db.refresh(card)
        return card


class InvestmentRepository:
    """Repository for Investment operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_investment(self, user_id: str, account_id: str, symbol: str,
                         name: str, investment_type: str, quantity: float,
                         purchase_price: float) -> Investment:
        """Create a new investment."""
        investment = Investment(
            user_id=user_id,
            account_id=account_id,
            symbol=symbol,
            name=name,
            investment_type=investment_type,
            quantity=quantity,
            purchase_price=purchase_price,
            purchase_date=datetime.utcnow()
        )
        self.db.add(investment)
        self.db.commit()
        self.db.refresh(investment)
        return investment
    
    def get_investment_by_id(self, investment_id: str) -> Optional[Investment]:
        """Get investment by ID."""
        return self.db.query(Investment).filter(Investment.id == investment_id).first()
    
    def get_investments_by_user_id(self, user_id: str) -> List[Investment]:
        """Get all investments for a user."""
        return self.db.query(Investment).filter(Investment.user_id == user_id).all()
    
    def get_investments_by_account_id(self, account_id: str) -> List[Investment]:
        """Get all investments for an account."""
        return self.db.query(Investment).filter(Investment.account_id == account_id).all()
    
    def update_current_price(self, investment_id: str, current_price: float) -> Optional[Investment]:
        """Update investment current price."""
        investment = self.get_investment_by_id(investment_id)
        if investment:
            investment.current_price = current_price
            self.db.commit()
            self.db.refresh(investment)
        return investment


class TransferRepository:
    """Repository for Transfer operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_transfer(self, user_id: str, from_account_id: str, to_account_id: str,
                       amount: float, currency: str = "USD", 
                       description: Optional[str] = None) -> Transfer:
        """Create a new transfer."""
        transfer = Transfer(
            user_id=user_id,
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=amount,
            currency=currency,
            description=description,
            status="pending"
        )
        self.db.add(transfer)
        self.db.commit()
        self.db.refresh(transfer)
        return transfer
    
    def get_transfer_by_id(self, transfer_id: str) -> Optional[Transfer]:
        """Get transfer by ID."""
        return self.db.query(Transfer).filter(Transfer.id == transfer_id).first()
    
    def get_transfers_by_user_id(self, user_id: str) -> List[Transfer]:
        """Get all transfers for a user."""
        return (self.db.query(Transfer)
                .filter(Transfer.user_id == user_id)
                .order_by(desc(Transfer.requested_date))
                .all())
    
    def update_transfer_status(self, transfer_id: str, status: str) -> Optional[Transfer]:
        """Update transfer status."""
        transfer = self.get_transfer_by_id(transfer_id)
        if transfer:
            transfer.status = status
            if status == "completed":
                transfer.completed_date = datetime.utcnow()
            elif status == "processing":
                transfer.processed_date = datetime.utcnow()
            self.db.commit()
            self.db.refresh(transfer)
        return transfer
