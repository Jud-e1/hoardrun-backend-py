"""
Base repository interface defining common data access patterns.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, TypeVar, Generic
from datetime import datetime

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository interface for data access operations."""
    
    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single record by ID."""
        pass
    
    @abstractmethod
    async def get_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve all records with pagination."""
        pass
    
    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new record."""
        pass
    
    @abstractmethod
    async def update(self, id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing record."""
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete a record by ID."""
        pass
    
    @abstractmethod
    async def find_by_criteria(self, criteria: Dict[str, Any], limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Find records matching specific criteria."""
        pass
    
    @abstractmethod
    async def count(self, criteria: Optional[Dict[str, Any]] = None) -> int:
        """Count records matching criteria."""
        pass
    
    @abstractmethod
    async def exists(self, id: str) -> bool:
        """Check if a record exists by ID."""
        pass


class UserFilterableRepository(BaseRepository[T]):
    """Repository interface for entities that belong to users."""
    
    @abstractmethod
    async def get_by_user_id(self, user_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve all records for a specific user."""
        pass
    
    @abstractmethod
    async def get_user_record(self, user_id: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific record for a user."""
        pass
    
    @abstractmethod
    async def count_by_user(self, user_id: str, criteria: Optional[Dict[str, Any]] = None) -> int:
        """Count records for a specific user."""
        pass


class TransactionRepository(UserFilterableRepository[T]):
    """Repository interface for transaction-related entities."""
    
    @abstractmethod
    async def get_by_date_range(
        self, 
        user_id: str, 
        start_date: datetime, 
        end_date: datetime,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve transactions within a date range."""
        pass
    
    @abstractmethod
    async def get_by_category(
        self, 
        user_id: str, 
        category: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve transactions by category."""
        pass
    
    @abstractmethod
    async def search_transactions(
        self,
        user_id: str,
        search_term: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search transactions by description or merchant."""
        pass
