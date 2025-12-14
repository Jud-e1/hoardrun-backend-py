"""
Mock repository implementation with in-memory storage and realistic financial data.
"""
import random
import uuid
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import Dict, List, Optional, Any
from enum import Enum

from .base import BaseRepository, UserFilterableRepository, TransactionRepository


class MockRepository(BaseRepository[Dict]):
    """Base mock repository with in-memory storage."""
    
    def __init__(self):
        self.data: Dict[str, Dict[str, Any]] = {}
        self.next_id = 1
    
    def _generate_id(self) -> str:
        """Generate a unique ID for new records."""
        return f"{self.__class__.__name__.lower().replace('repository', '')}_{self.next_id:06d}_{uuid.uuid4().hex[:8]}"
    
    async def get_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single record by ID."""
        return self.data.get(id)
    
    async def get_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve all records with pagination."""
        items = list(self.data.values())[offset:offset + limit]
        return items
    
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new record."""
        if "id" not in data or not data["id"]:
            data["id"] = self._generate_id()
        
        now = datetime.now(UTC)
        data["created_at"] = now
        data["updated_at"] = now
        
        self.data[data["id"]] = data
        self.next_id += 1
        return data
    
    async def update(self, id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing record."""
        if id not in self.data:
            return None
        
        # Merge updates with existing data
        updated_data = {**self.data[id], **data}
        updated_data["updated_at"] = datetime.now(UTC)
        
        self.data[id] = updated_data
        return updated_data
    
    async def delete(self, id: str) -> bool:
        """Delete a record by ID."""
        if id in self.data:
            del self.data[id]
            return True
        return False
    
    async def find_by_criteria(self, criteria: Dict[str, Any], limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Find records matching specific criteria."""
        matches = []
        for record in self.data.values():
            if self._matches_criteria(record, criteria):
                matches.append(record)
        
        return matches[offset:offset + limit]
    
    async def count(self, criteria: Optional[Dict[str, Any]] = None) -> int:
        """Count records matching criteria."""
        if not criteria:
            return len(self.data)
        
        count = 0
        for record in self.data.values():
            if self._matches_criteria(record, criteria):
                count += 1
        
        return count
    
    async def exists(self, id: str) -> bool:
        """Check if a record exists by ID."""
        return id in self.data
    
    def _matches_criteria(self, record: Dict[str, Any], criteria: Dict[str, Any]) -> bool:
        """Check if a record matches the given criteria."""
        for key, value in criteria.items():
            if key not in record:
                return False
            
            record_value = record[key]
            
            # Handle different comparison types
            if isinstance(value, dict):
                if "$gte" in value and record_value < value["$gte"]:
                    return False
                if "$lte" in value and record_value > value["$lte"]:
                    return False
                if "$gt" in value and record_value <= value["$gt"]:
                    return False
                if "$lt" in value and record_value >= value["$lt"]:
                    return False
                if "$in" in value and record_value not in value["$in"]:
                    return False
                if "$regex" in value:
                    import re
                    if not re.search(value["$regex"], str(record_value), re.IGNORECASE):
                        return False
            else:
                if record_value != value:
                    return False
        
        return True


class UserMockRepository(MockRepository, UserFilterableRepository[Dict]):
    """Mock repository for user-specific entities."""
    
    async def get_by_user_id(self, user_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve all records for a specific user."""
        return await self.find_by_criteria({"user_id": user_id}, limit, offset)
    
    async def get_user_record(self, user_id: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific record for a user."""
        record = await self.get_by_id(record_id)
        if record and record.get("user_id") == user_id:
            return record
        return None
    
    async def count_by_user(self, user_id: str, criteria: Optional[Dict[str, Any]] = None) -> int:
        """Count records for a specific user."""
        user_criteria = {"user_id": user_id}
        if criteria:
            user_criteria.update(criteria)
        return await self.count(user_criteria)


class TransactionMockRepository(UserMockRepository, TransactionRepository[Dict]):
    """Mock repository for transaction entities with advanced querying."""
    
    async def get_by_date_range(
        self, 
        user_id: str, 
        start_date: datetime, 
        end_date: datetime,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve transactions within a date range."""
        criteria = {
            "user_id": user_id,
            "transaction_date": {
                "$gte": start_date,
                "$lte": end_date
            }
        }
        return await self.find_by_criteria(criteria, limit, offset)
    
    async def get_by_category(
        self, 
        user_id: str, 
        category: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve transactions by category."""
        criteria = {
            "user_id": user_id,
            "category": category
        }
        return await self.find_by_criteria(criteria, limit, offset)
    
    async def search_transactions(
        self,
        user_id: str,
        search_term: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search transactions by description or merchant."""
        matches = []
        search_term_lower = search_term.lower()
        
        for record in self.data.values():
            if record.get("user_id") != user_id:
                continue
            
            # Search in description and merchant fields
            description = str(record.get("description", "")).lower()
            merchant = str(record.get("merchant", "")).lower()
            
            if search_term_lower in description or search_term_lower in merchant:
                matches.append(record)
        
        # Sort by date (most recent first)
        matches.sort(key=lambda x: x.get("transaction_date", datetime.min), reverse=True)
        
        return matches[offset:offset + limit]


# Repository instances
class RepositoryManager:
    """Central repository manager for all data access."""
    
    def __init__(self):
        self.accounts = UserMockRepository()
        self.cards = UserMockRepository()
        self.transactions = TransactionMockRepository()
        self.transfers = UserMockRepository()
        self.investments = UserMockRepository()
        self.savings_goals = UserMockRepository()
        self.savings_accounts = UserMockRepository()
        self.beneficiaries = UserMockRepository()
        self.notifications = UserMockRepository()
        self.settings = UserMockRepository()
        self.watchlist = UserMockRepository()
        self.plaid_connections = UserMockRepository()
        self.plaid_accounts = UserMockRepository()
        self.plaid_transactions = UserMockRepository()
        self.plaid_link_tokens = UserMockRepository()
        
        # Flag to track if mock data has been initialized
        self._mock_data_initialized = False
    
    async def ensure_mock_data_initialized(self):
        """Ensure mock data is initialized (lazy initialization)."""
        if not self._mock_data_initialized:
            await self._setup_mock_data()
            self._mock_data_initialized = True
    
    async def _setup_mock_data(self):
        """Setup realistic mock data for all entities."""
        
        # Sample user IDs for testing
        user_ids = ["user_001", "user_002", "user_003"]
        
        for user_id in user_ids:
            await self._create_user_accounts(user_id)
            await self._create_user_cards(user_id)
            await self._create_user_transactions(user_id)
            await self._create_user_investments(user_id)
            await self._create_user_savings(user_id)
            await self._create_user_settings(user_id)
    
    async def _create_user_accounts(self, user_id: str):
        """Create mock accounts for a user."""
        accounts = [
            {
                "user_id": user_id,
                "account_type": "checking",
                "account_number": f"CHK{random.randint(100000, 999999)}",
                "balance": Decimal(str(random.uniform(1000, 50000))),
                "available_balance": Decimal(str(random.uniform(800, 48000))),
                "currency": "USD",
                "status": "active",
                "bank_name": random.choice(["Chase Bank", "Bank of America", "Wells Fargo", "Citi Bank"]),
                "account_name": "Primary Checking",
                "interest_rate": Decimal("0.01"),
                "monthly_fee": Decimal("0.00"),
            },
            {
                "user_id": user_id,
                "account_type": "savings",
                "account_number": f"SAV{random.randint(100000, 999999)}",
                "balance": Decimal(str(random.uniform(5000, 100000))),
                "available_balance": Decimal(str(random.uniform(5000, 100000))),
                "currency": "USD",
                "status": "active",
                "bank_name": random.choice(["Chase Bank", "Bank of America", "Wells Fargo", "Citi Bank"]),
                "account_name": "High Yield Savings",
                "interest_rate": Decimal("4.5"),
                "monthly_fee": Decimal("0.00"),
            }
        ]
        
        for account in accounts:
            await self.accounts.create(account)
    
    async def _create_user_cards(self, user_id: str):
        """Create mock cards for a user."""
        user_accounts = await self.accounts.get_by_user_id(user_id)
        
        cards = [
            {
                "user_id": user_id,
                "card_number": "****-****-****-1234",
                "full_card_number": "4532123456781234",  # For internal use only
                "card_type": "debit",
                "brand": "Visa",
                "status": "active",
                "linked_account_id": user_accounts[0]["id"] if user_accounts else None,
                "expiry_date": (datetime.now() + timedelta(days=365*2)).strftime("%m/%y"),
                "daily_limit": Decimal("5000.00"),
                "monthly_limit": Decimal("50000.00"),
                "current_daily_spent": Decimal(str(random.uniform(0, 1000))),
                "current_monthly_spent": Decimal(str(random.uniform(0, 10000))),
                "is_frozen": False,
                "card_name": "Primary Debit Card",
            },
            {
                "user_id": user_id,
                "card_number": "****-****-****-5678",
                "full_card_number": "5432876543215678",
                "card_type": "credit",
                "brand": "Mastercard",
                "status": "active",
                "linked_account_id": None,
                "expiry_date": (datetime.now() + timedelta(days=365*3)).strftime("%m/%y"),
                "daily_limit": Decimal("10000.00"),
                "monthly_limit": Decimal("100000.00"),
                "current_daily_spent": Decimal(str(random.uniform(0, 2000))),
                "current_monthly_spent": Decimal(str(random.uniform(0, 20000))),
                "credit_limit": Decimal("25000.00"),
                "available_credit": Decimal(str(random.uniform(15000, 25000))),
                "is_frozen": False,
                "card_name": "Rewards Credit Card",
            }
        ]
        
        for card in cards:
            await self.cards.create(card)
    
    async def _create_user_transactions(self, user_id: str):
        """Create mock transactions for a user."""
        user_accounts = await self.accounts.get_by_user_id(user_id)
        user_cards = await self.cards.get_by_user_id(user_id)
        
        categories = ["groceries", "restaurants", "gas", "shopping", "entertainment", "utilities", "healthcare", "transport"]
        merchants = [
            "Walmart", "Amazon", "Starbucks", "McDonald's", "Shell", "Target", "Uber", "Netflix",
            "Apple Store", "Google Play", "Home Depot", "CVS Pharmacy", "Spotify", "Whole Foods"
        ]
        
        # Generate transactions for the last 90 days
        for i in range(50):
            transaction_date = datetime.now(UTC) - timedelta(days=random.randint(0, 90))
            
            transaction = {
                "user_id": user_id,
                "account_id": random.choice(user_accounts)["id"] if user_accounts else None,
                "card_id": random.choice(user_cards)["id"] if user_cards and random.random() > 0.3 else None,
                "amount": Decimal(str(random.uniform(5.99, 500.00))),
                "currency": "USD",
                "transaction_type": random.choice(["debit", "credit"]),
                "category": random.choice(categories),
                "merchant": random.choice(merchants),
                "description": f"Payment to {random.choice(merchants)}",
                "transaction_date": transaction_date,
                "status": random.choice(["completed", "pending"]) if random.random() > 0.9 else "completed",
                "reference_number": f"TXN{random.randint(100000000, 999999999)}",
                "location": random.choice(["New York, NY", "Los Angeles, CA", "Chicago, IL", "Houston, TX"]),
                "is_recurring": random.random() > 0.85,
            }
            
            await self.transactions.create(transaction)
    
    async def _create_user_investments(self, user_id: str):
        """Create mock investment data for a user."""
        stocks = [
            {"symbol": "AAPL", "name": "Apple Inc.", "price": 182.50, "change": 2.3},
            {"symbol": "GOOGL", "name": "Alphabet Inc.", "price": 142.80, "change": -1.2},
            {"symbol": "MSFT", "name": "Microsoft Corporation", "price": 378.85, "change": 5.4},
            {"symbol": "TSLA", "name": "Tesla Inc.", "price": 248.50, "change": -3.8},
            {"symbol": "AMZN", "name": "Amazon.com Inc.", "price": 145.30, "change": 1.7},
        ]
        
        # Create portfolio holdings
        for stock in stocks[:3]:  # User holds first 3 stocks
            holding = {
                "user_id": user_id,
                "symbol": stock["symbol"],
                "company_name": stock["name"],
                "shares": Decimal(str(random.randint(5, 100))),
                "avg_purchase_price": Decimal(str(stock["price"] * random.uniform(0.8, 1.2))),
                "current_price": Decimal(str(stock["price"])),
                "market_value": Decimal(str(stock["price"] * random.randint(5, 100))),
                "unrealized_gain_loss": Decimal(str(random.uniform(-1000, 2000))),
                "purchase_date": datetime.now(UTC) - timedelta(days=random.randint(30, 365)),
            }
            await self.investments.create(holding)
        
        # Create watchlist
        for stock in stocks[3:]:  # Remaining stocks in watchlist
            watchlist_item = {
                "user_id": user_id,
                "symbol": stock["symbol"],
                "company_name": stock["name"],
                "current_price": Decimal(str(stock["price"])),
                "target_price": Decimal(str(stock["price"] * random.uniform(1.1, 1.3))),
                "alert_enabled": True,
            }
            await self.watchlist.create(watchlist_item)
    
    async def _create_user_savings(self, user_id: str):
        """Create mock savings data for a user."""
        savings_goals = [
            {
                "user_id": user_id,
                "goal_name": "Emergency Fund",
                "target_amount": Decimal("10000.00"),
                "current_amount": Decimal(str(random.uniform(2000, 8000))),
                "target_date": datetime.now(UTC) + timedelta(days=365),
                "monthly_contribution": Decimal("500.00"),
                "auto_save_enabled": True,
                "auto_save_amount": Decimal("100.00"),
                "auto_save_frequency": "weekly",
            },
            {
                "user_id": user_id,
                "goal_name": "Vacation Fund",
                "target_amount": Decimal("5000.00"),
                "current_amount": Decimal(str(random.uniform(500, 3000))),
                "target_date": datetime.now(UTC) + timedelta(days=180),
                "monthly_contribution": Decimal("300.00"),
                "auto_save_enabled": False,
                "auto_save_amount": Decimal("0.00"),
                "auto_save_frequency": "none",
            }
        ]
        
        for goal in savings_goals:
            await self.savings_goals.create(goal)
        
        # Create savings accounts
        savings_account = {
            "user_id": user_id,
            "account_name": "High Yield Savings",
            "balance": Decimal(str(random.uniform(10000, 50000))),
            "interest_rate": Decimal("4.50"),
            "compound_frequency": "monthly",
            "minimum_balance": Decimal("1000.00"),
            "monthly_fee": Decimal("0.00"),
            "last_interest_date": datetime.now(UTC) - timedelta(days=30),
        }
        await self.savings_accounts.create(savings_account)
    
    async def _create_user_settings(self, user_id: str):
        """Create mock user settings."""
        user_settings = {
            "user_id": user_id,
            "profile": {
                "first_name": f"User{user_id[-3:]}",
                "last_name": "Demo",
                "email": f"user{user_id[-3:]}@example.com",
                "phone": f"+1{random.randint(1000000000, 9999999999)}",
                "date_of_birth": "1990-01-01",
                "address": {
                    "street": "123 Main St",
                    "city": "Anytown",
                    "state": "CA",
                    "zip_code": "12345",
                    "country": "US"
                }
            },
            "preferences": {
                "currency": "USD",
                "language": "en",
                "timezone": "America/New_York",
                "date_format": "MM/DD/YYYY",
                "number_format": "US",
                "theme": "light",
            },
            "security": {
                "two_factor_enabled": True,
                "biometric_enabled": True,
                "session_timeout": 30,
                "login_notifications": True,
                "transaction_notifications": True,
            },
            "notifications": {
                "email_enabled": True,
                "sms_enabled": True,
                "push_enabled": True,
                "transaction_alerts": True,
                "spending_limit_alerts": True,
                "investment_alerts": True,
                "news_updates": False,
            }
        }
        await self.settings.create(user_settings)


# Global repository manager instance
repository_manager = RepositoryManager()


def get_repository_manager() -> RepositoryManager:
    """Get the global repository manager instance."""
    return repository_manager


# Individual repository getters for dependency injection
def get_accounts_repository() -> UserMockRepository:
    """Get accounts repository."""
    return repository_manager.accounts


def get_cards_repository() -> UserMockRepository:
    """Get cards repository."""
    return repository_manager.cards


def get_transactions_repository() -> TransactionMockRepository:
    """Get transactions repository."""
    return repository_manager.transactions


def get_transfers_repository() -> UserMockRepository:
    """Get transfers repository."""
    return repository_manager.transfers


def get_investments_repository() -> UserMockRepository:
    """Get investments repository."""
    return repository_manager.investments


def get_savings_goals_repository() -> UserMockRepository:
    """Get savings goals repository."""
    return repository_manager.savings_goals


def get_savings_accounts_repository() -> UserMockRepository:
    """Get savings accounts repository."""
    return repository_manager.savings_accounts


def get_beneficiaries_repository() -> UserMockRepository:
    """Get beneficiaries repository."""
    return repository_manager.beneficiaries


def get_notifications_repository() -> UserMockRepository:
    """Get notifications repository."""
    return repository_manager.notifications


def get_settings_repository() -> UserMockRepository:
    """Get settings repository."""
    return repository_manager.settings


def get_watchlist_repository() -> UserMockRepository:
    """Get watchlist repository."""
    return repository_manager.watchlist


def get_plaid_connections_repository() -> UserMockRepository:
    """Get Plaid connections repository."""
    return repository_manager.plaid_connections


def get_plaid_accounts_repository() -> UserMockRepository:
    """Get Plaid accounts repository."""
    return repository_manager.plaid_accounts


def get_plaid_transactions_repository() -> TransactionMockRepository:
    """Get Plaid transactions repository."""
    return repository_manager.plaid_transactions


def get_plaid_link_tokens_repository() -> UserMockRepository:
    """Get Plaid link tokens repository."""
    return repository_manager.plaid_link_tokens


# Plaid Transfer specific methods
async def create_transfer_quote(quote_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a transfer quote."""
    return await repository_manager.transfers.create(quote_data)

async def get_transfer_quote(quote_id: str) -> Optional[Dict[str, Any]]:
    """Get a transfer quote by ID."""
    return await repository_manager.transfers.get_by_id(quote_id)
