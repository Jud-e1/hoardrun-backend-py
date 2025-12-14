"""
Transaction management service - Plaid-based implementation.
Now uses Plaid as the primary source for transaction data.
"""

import uuid
import time
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from difflib import SequenceMatcher

from ..models.transaction import (
    Transaction, TransactionType, TransactionStatus, TransactionDirection,
    MerchantCategory, PaymentMethod, TransactionSummary,
    TransactionListRequest, TransactionSearchRequest, TransactionUpdateRequest,
    TransactionDisputeRequest, TransactionCategorizeRequest, TransactionExportRequest,
    TransactionCategoryStats
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


class TransactionService:
    """Service for managing financial transactions via Plaid."""
    
    def __init__(self):
        self.repo = get_repository_manager()
        self.plaid_service = get_plaid_service()
    
    async def list_transactions(
        self, 
        user_id: str, 
        request: TransactionListRequest
    ) -> Dict[str, Any]:
        """
        List Plaid transactions with filtering, sorting, and pagination.
        
        Args:
            user_id: User identifier
            request: Transaction listing request with filters
            
        Returns:
            Paginated transaction list with summary
        """
        logger.info(f"Listing Plaid transactions for user {user_id}")
        
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        
        plaid_accounts = await self.plaid_service.get_user_accounts(user_id)
        
        all_transactions = []
        for account in plaid_accounts:
            # Filter by account if specified
            if request.account_id and account.account_id != request.account_id:
                continue
            
            connection = await self.repo.get_plaid_connection(account.connection_id)
            
            # Get transactions for date range
            start_date = request.start_date or (date.today() - timedelta(days=90))
            end_date = request.end_date or date.today()
            
            plaid_transactions = await self.repo.get_plaid_transactions_by_date_range(
                connection.connection_id,
                start_date,
                end_date
            )
            
            # Filter for this account
            account_transactions = [t for t in plaid_transactions if t.account_id == account.account_id]
            all_transactions.extend(account_transactions)
        
        # Apply additional filters
        filtered_transactions = await self._apply_filters(all_transactions, request)
        
        # Apply search query if provided
        if request.search_query:
            filtered_transactions = self._apply_search(filtered_transactions, request.search_query)
        
        # Sort transactions
        sorted_transactions = self._sort_transactions(
            filtered_transactions, request.sort_by, request.sort_order
        )
        
        # Apply pagination
        total_count = len(sorted_transactions)
        paginated_transactions = sorted_transactions[request.offset:request.offset + request.limit]
        
        # Generate summary
        summary = self._calculate_transaction_summary(
            filtered_transactions, request.start_date, request.end_date
        )
        
        has_more = (request.offset + request.limit) < total_count
        
        logger.info(f"Found {total_count} Plaid transactions, returning {len(paginated_transactions)}")
        return {
            "transactions": paginated_transactions,
            "total_count": total_count,
            "summary": summary,
            "has_more": has_more
        }
    
    async def get_transaction_details(self, transaction_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific Plaid transaction.
        
        Args:
            transaction_id: Plaid transaction identifier
            user_id: User identifier
            
        Returns:
            Transaction details from Plaid
        """
        logger.info(f"Getting Plaid transaction details for {transaction_id}")
        
        transaction = await self.repo.get_plaid_transaction(transaction_id)
        if not transaction:
            raise NotFoundError(f"Plaid transaction {transaction_id} not found")
        
        # Verify ownership
        connection = await self.repo.get_plaid_connection(transaction.connection_id)
        if connection.user_id != user_id:
            raise UnauthorizedError("You don't have access to this transaction")
        
        return transaction
    
    async def search_transactions(
        self, 
        user_id: str, 
        request: TransactionSearchRequest
    ) -> Dict[str, Any]:
        """
        Advanced search for Plaid transactions with fuzzy matching.
        
        Args:
            user_id: User identifier
            request: Search request
            
        Returns:
            Search results with timing and suggestions
        """
        start_time = time.time()
        logger.info(f"Searching Plaid transactions for user {user_id}: '{request.query}'")
        
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        
        plaid_accounts = await self.plaid_service.get_user_accounts(user_id)
        
        all_transactions = []
        for account in plaid_accounts:
            connection = await self.repo.get_plaid_connection(account.connection_id)
            
            # Get recent transactions (last 90 days)
            start_date = date.today() - timedelta(days=90)
            end_date = date.today()
            
            plaid_transactions = await self.repo.get_plaid_transactions_by_date_range(
                connection.connection_id,
                start_date,
                end_date
            )
            
            account_transactions = [t for t in plaid_transactions if t.account_id == account.account_id]
            all_transactions.extend(account_transactions)
        
        # Apply additional filters if provided
        if request.filters:
            all_transactions = await self._apply_filters(all_transactions, request.filters)
        
        # Perform search
        matching_transactions = []
        for transaction in all_transactions:
            if self._matches_search_query(transaction, request.query, request.search_fields, request.fuzzy_match):
                matching_transactions.append(transaction)
        
        # Generate search suggestions
        suggestions = self._generate_search_suggestions(request.query, all_transactions)
        
        search_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        logger.info(f"Search completed in {search_time:.2f}ms, found {len(matching_transactions)} matches")
        return {
            "transactions": matching_transactions,
            "total_matches": len(matching_transactions),
            "search_time_ms": search_time,
            "suggestions": suggestions
        }
    
    async def update_transaction(
        self, 
        transaction_id: str, 
        user_id: str, 
        request: TransactionUpdateRequest
    ) -> Dict[str, Any]:
        """
        Update transaction metadata (user-editable fields only).
        Note: Plaid transaction data itself cannot be modified.
        
        Args:
            transaction_id: Plaid transaction identifier
            user_id: User identifier
            request: Update request
            
        Returns:
            Updated transaction metadata
        """
        logger.info(f"Updating Plaid transaction metadata for {transaction_id}")
        
        transaction = await self.get_transaction_details(transaction_id, user_id)
        
        metadata = await self.repo.get_transaction_metadata(transaction_id) or {}
        
        # Update editable metadata fields
        if request.description is not None:
            metadata["custom_description"] = request.description
        
        if request.merchant_category is not None:
            metadata["custom_category"] = request.merchant_category
        
        if request.tags is not None:
            metadata["tags"] = request.tags
        
        if request.notes is not None:
            metadata["notes"] = request.notes
        
        metadata["updated_at"] = datetime.utcnow()
        
        await self.repo.save_transaction_metadata(transaction_id, metadata)
        
        logger.info(f"Plaid transaction metadata {transaction_id} updated successfully")
        
        # Return transaction with metadata overlay
        return {
            **transaction.__dict__,
            "metadata": metadata
        }
    
    
    async def get_transaction_analytics(
        self, 
        user_id: str,
        account_id: Optional[str] = None,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        Get comprehensive transaction analytics from Plaid data.
        
        Args:
            user_id: User identifier
            account_id: Optional account filter
            days: Analysis period in days
            
        Returns:
            Transaction analytics and insights
        """
        logger.info(f"Getting Plaid transaction analytics for user {user_id}")
        
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        
        # Calculate period
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        plaid_accounts = await self.plaid_service.get_user_accounts(user_id)
        
        transactions = []
        for account in plaid_accounts:
            if account_id and account.account_id != account_id:
                continue
            
            connection = await self.repo.get_plaid_connection(account.connection_id)
            
            plaid_transactions = await self.repo.get_plaid_transactions_by_date_range(
                connection.connection_id,
                start_date,
                end_date
            )
            
            account_transactions = [t for t in plaid_transactions if t.account_id == account.account_id]
            transactions.extend(account_transactions)
        
        # Calculate analytics
        analytics = await self._calculate_comprehensive_analytics(
            transactions, start_date, end_date
        )
        analytics["account_id"] = account_id
        
        logger.info(f"Analytics calculated for {len(transactions)} Plaid transactions")
        return analytics
    
    
    async def get_recent_transactions(
        self, 
        user_id: str, 
        limit: int = 10,
        account_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get most recent Plaid transactions for quick access.
        
        Args:
            user_id: User identifier
            limit: Number of transactions to return
            account_id: Optional account filter
            
        Returns:
            List of recent Plaid transactions
        """
        logger.info(f"Getting {limit} recent Plaid transactions for user {user_id}")
        
        # Create request for recent transactions
        request = TransactionListRequest(
            account_id=account_id,
            limit=limit,
            offset=0,
            sort_by="transaction_date",
            sort_order="desc"
        )
        
        result = await self.list_transactions(user_id, request)
        return result["transactions"]
    
    
    # Private helper methods remain mostly the same but work with Plaid transaction format
    async def _apply_filters(
        self, 
        transactions: List[Any], 
        request: TransactionListRequest
    ) -> List[Any]:
        """Apply filtering criteria to Plaid transactions."""
        filtered = []
        
        for transaction in transactions:
            # Amount range filter (Plaid uses positive for debits, negative for credits)
            abs_amount = abs(transaction.amount)
            if request.min_amount and abs_amount < request.min_amount:
                continue
            if request.max_amount and abs_amount > request.max_amount:
                continue
            
            # Pending filter
            if hasattr(request, 'include_pending') and not request.include_pending:
                if transaction.pending:
                    continue
            
            filtered.append(transaction)
        
        return filtered
    
    def _apply_search(self, transactions: List[Any], query: str) -> List[Any]:
        """Apply text search to Plaid transactions."""
        query_lower = query.lower()
        matching = []
        
        for transaction in transactions:
            # Search in transaction name
            if query_lower in transaction.name.lower():
                matching.append(transaction)
                continue
            
            # Search in merchant name
            if transaction.merchant_name and query_lower in transaction.merchant_name.lower():
                matching.append(transaction)
                continue
        
        return matching
    
    def _sort_transactions(
        self, 
        transactions: List[Any], 
        sort_by: str, 
        sort_order: str
    ) -> List[Any]:
        """Sort Plaid transactions by specified field and order."""
        reverse = sort_order.lower() == "desc"
        
        try:
            if sort_by == "amount":
                return sorted(transactions, key=lambda x: abs(x.amount), reverse=reverse)
            elif sort_by == "merchant_name":
                return sorted(transactions, key=lambda x: x.merchant_name or "", reverse=reverse)
            else:  # Default to date
                return sorted(transactions, key=lambda x: x.date, reverse=reverse)
        except Exception as e:
            logger.warning(f"Failed to sort by {sort_by}, using default sort: {e}")
            return sorted(transactions, key=lambda x: x.date, reverse=True)
    
    def _calculate_transaction_summary(
        self, 
        transactions: List[Any],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> TransactionSummary:
        """Calculate summary statistics for Plaid transactions."""
        if not transactions:
            return TransactionSummary(
                period_start=start_date or date.today(),
                period_end=end_date or date.today(),
                total_transactions=0,
                total_amount=Decimal("0"),
                total_credits=Decimal("0"),
                total_debits=Decimal("0")
            )
        
        # Plaid: positive = debit, negative = credit
        total_amount = sum(abs(t.amount) for t in transactions)
        total_debits = sum(t.amount for t in transactions if t.amount > 0)
        total_credits = abs(sum(t.amount for t in transactions if t.amount < 0))
        average_transaction = total_amount / len(transactions) if transactions else Decimal("0")
        largest_transaction = max(abs(t.amount) for t in transactions) if transactions else Decimal("0")
        
        # Calculate by merchant
        by_merchant = {}
        for transaction in transactions:
            merchant = transaction.merchant_name or transaction.name or "Unknown"
            amount = abs(transaction.amount)
            by_merchant[merchant] = by_merchant.get(merchant, Decimal("0")) + amount
        
        # Get top 10 merchants
        top_merchants = dict(sorted(by_merchant.items(), key=lambda x: x[1], reverse=True)[:10])
        
        return TransactionSummary(
            period_start=start_date or min(t.date for t in transactions),
            period_end=end_date or max(t.date for t in transactions),
            total_transactions=len(transactions),
            total_amount=total_amount,
            total_credits=total_credits,
            total_debits=total_debits,
            average_transaction=average_transaction,
            largest_transaction=largest_transaction,
            by_merchant=top_merchants
        )
    
    async def _calculate_comprehensive_analytics(
        self, 
        transactions: List[Any],
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Calculate comprehensive analytics from Plaid transactions."""
        
        # Calculate spending (positive amounts in Plaid)
        total_spending = sum(t.amount for t in transactions if t.amount > 0)
        
        # Monthly trends
        monthly_trends = {}
        current_date = start_date
        while current_date <= end_date:
            month_key = current_date.strftime("%Y-%m")
            month_transactions = [
                t for t in transactions 
                if t.date.strftime("%Y-%m") == month_key and t.amount > 0
            ]
            monthly_trends[month_key] = sum(t.amount for t in month_transactions)
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        # Top merchants
        merchant_spending = {}
        for transaction in transactions:
            if transaction.amount > 0:  # Spending only
                merchant = transaction.merchant_name or transaction.name or "Unknown"
                amount = transaction.amount
                merchant_spending[merchant] = merchant_spending.get(merchant, Decimal("0")) + amount
        
        top_merchants = dict(sorted(merchant_spending.items(), key=lambda x: x[1], reverse=True)[:10])
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "total_transactions": len(transactions),
            "monthly_trends": monthly_trends,
            "top_merchants": top_merchants
        }
    
    def _matches_search_query(
        self, 
        transaction: Any, 
        query: str, 
        search_fields: List[str], 
        fuzzy_match: bool
    ) -> bool:
        """Check if Plaid transaction matches search query."""
        query_lower = query.lower()
        
        for field in search_fields:
            field_value = ""
            
            if field == "description" or field == "name":
                field_value = transaction.name
            elif field == "merchant_name":
                field_value = transaction.merchant_name or ""
            
            field_value_lower = field_value.lower()
            
            if fuzzy_match:
                similarity = SequenceMatcher(None, query_lower, field_value_lower).ratio()
                if similarity > 0.6:
                    return True
            else:
                if query_lower in field_value_lower:
                    return True
        
        return False
    
    def _generate_search_suggestions(
        self, 
        query: str, 
        transactions: List[Any]
    ) -> List[str]:
        """Generate search suggestions based on Plaid transaction data."""
        suggestions = set()
        query_lower = query.lower()
        
        for transaction in transactions[:100]:  # Limit for performance
            # From transaction name
            words = transaction.name.lower().split()
            for word in words:
                if len(word) > 3 and query_lower in word:
                    suggestions.add(word)
            
            # From merchant name
            if transaction.merchant_name:
                merchant_words = transaction.merchant_name.lower().split()
                for word in merchant_words:
                    if len(word) > 3 and query_lower in word:
                        suggestions.add(word)
        
        return sorted(list(suggestions))[:5]


# Dependency provider
def get_transaction_service() -> TransactionService:
    """Dependency provider for transaction service."""
    return TransactionService()


