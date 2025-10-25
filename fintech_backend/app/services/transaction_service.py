"""
Transaction management service for the fintech backend.
"""

import uuid
import time
import random
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import asyncio
from difflib import SequenceMatcher

from ..models.transaction import (
    Transaction, TransactionType, TransactionStatus, TransactionDirection,
    MerchantCategory, PaymentMethod, TransactionDetails, TransactionSummary,
    TransactionListRequest, TransactionSearchRequest, TransactionUpdateRequest,
    TransactionDisputeRequest, TransactionCategorizeRequest, TransactionExportRequest,
    TransactionCategoryStats, BalanceHistoryPoint
)
from ..core.exceptions import (
    ValidationError, NotFoundError, BusinessLogicError,
    UnauthorizedError
)
from ..data.repository import get_repository_manager
from ..utils.validators import validate_user_exists, validate_account_exists
from ..config.logging import get_logger

logger = get_logger(__name__)


class TransactionService:
    """Service for managing financial transactions and analytics."""
    
    def __init__(self):
        self.repo = get_repository_manager()
    
    async def list_transactions(
        self, 
        user_id: str, 
        request: TransactionListRequest
    ) -> Dict[str, Any]:
        """
        List transactions with filtering, sorting, and pagination.
        
        Args:
            user_id: User identifier
            request: Transaction listing request with filters
            
        Returns:
            Paginated transaction list with summary
        """
        logger.info(f"Listing transactions for user {user_id}")
        
        # Validate user exists
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        
        # Get user transactions
        all_transactions = await self.repo.get_user_transactions(user_id)
        
        # Apply filters
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
        
        logger.info(f"Found {total_count} transactions, returning {len(paginated_transactions)}")
        return {
            "transactions": paginated_transactions,
            "total_count": total_count,
            "summary": summary,
            "has_more": has_more
        }
    
    async def get_transaction_details(self, transaction_id: str, user_id: str) -> Transaction:
        """
        Get detailed information for a specific transaction.
        
        Args:
            transaction_id: Transaction identifier
            user_id: User identifier
            
        Returns:
            Transaction details
        """
        logger.info(f"Getting transaction details for {transaction_id}")
        
        transaction = await self.repo.get_transaction_by_id(transaction_id)
        if not transaction:
            raise NotFoundError(f"Transaction {transaction_id} not found")
        
        # Verify ownership
        if transaction.user_id != user_id:
            raise UnauthorizedError("You don't have access to this transaction")
        
        return transaction
    
    async def search_transactions(
        self, 
        user_id: str, 
        request: TransactionSearchRequest
    ) -> Dict[str, Any]:
        """
        Advanced search for transactions with fuzzy matching.
        
        Args:
            user_id: User identifier
            request: Search request
            
        Returns:
            Search results with timing and suggestions
        """
        start_time = time.time()
        logger.info(f"Searching transactions for user {user_id}: '{request.query}'")
        
        # Validate user exists
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        
        # Get user transactions
        all_transactions = await self.repo.get_user_transactions(user_id)
        
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
    ) -> Transaction:
        """
        Update transaction details (user-editable fields only).
        
        Args:
            transaction_id: Transaction identifier
            user_id: User identifier
            request: Update request
            
        Returns:
            Updated transaction
        """
        logger.info(f"Updating transaction {transaction_id}")
        
        transaction = await self.get_transaction_details(transaction_id, user_id)
        
        # Check if transaction can be updated
        if transaction.status in [TransactionStatus.CANCELLED, TransactionStatus.REVERSED]:
            raise BusinessLogicError("Cannot update cancelled or reversed transaction")
        
        # Update editable fields
        if request.description is not None:
            transaction.description = request.description
        
        if request.merchant_category is not None:
            transaction.merchant_category = request.merchant_category
        
        if request.tags is not None:
            transaction.tags = request.tags
        
        if request.notes is not None:
            transaction.notes = request.notes
        
        transaction.updated_at = datetime.utcnow()
        await self.repo.update_transaction(transaction)
        
        logger.info(f"Transaction {transaction_id} updated successfully")
        return transaction
    
    async def categorize_transactions(
        self, 
        user_id: str, 
        request: TransactionCategorizeRequest
    ) -> Dict[str, Any]:
        """
        Batch categorize multiple transactions.
        
        Args:
            user_id: User identifier
            request: Categorization request
            
        Returns:
            Update results with counts
        """
        logger.info(f"Bulk categorizing {len(request.transaction_ids)} transactions")
        
        updated_count = 0
        failed_count = 0
        failed_transactions = []
        similar_updated = 0
        
        # Update each transaction
        for transaction_id in request.transaction_ids:
            try:
                transaction = await self.get_transaction_details(transaction_id, user_id)
                transaction.merchant_category = request.category
                transaction.updated_at = datetime.utcnow()
                await self.repo.update_transaction(transaction)
                updated_count += 1
                
                # If apply_to_similar is True, find and update similar transactions
                if request.apply_to_similar:
                    similar_count = await self._update_similar_transactions(
                        user_id, transaction, request.category
                    )
                    similar_updated += similar_count
                    
            except Exception as e:
                logger.error(f"Failed to update transaction {transaction_id}: {e}")
                failed_count += 1
                failed_transactions.append(transaction_id)
        
        logger.info(f"Categorization complete: {updated_count} updated, {failed_count} failed")
        return {
            "updated_count": updated_count,
            "failed_count": failed_count,
            "failed_transactions": failed_transactions,
            "similar_updated": similar_updated
        }
    
    async def dispute_transaction(
        self, 
        transaction_id: str, 
        user_id: str, 
        request: TransactionDisputeRequest
    ) -> Dict[str, Any]:
        """
        Initiate a dispute for a transaction.
        
        Args:
            transaction_id: Transaction identifier
            user_id: User identifier
            request: Dispute request
            
        Returns:
            Dispute case information
        """
        logger.info(f"Initiating dispute for transaction {transaction_id}")
        
        transaction = await self.get_transaction_details(transaction_id, user_id)
        
        # Validate transaction can be disputed
        if transaction.status != TransactionStatus.COMPLETED:
            raise BusinessLogicError("Can only dispute completed transactions")
        
        if transaction.is_disputed:
            raise BusinessLogicError("Transaction is already under dispute")
        
        # Check dispute time window (90 days)
        days_since_transaction = (datetime.utcnow() - transaction.transaction_date).days
        if days_since_transaction > 90:
            raise BusinessLogicError("Dispute window has expired (90 days)")
        
        # Create dispute case
        dispute_id = str(uuid.uuid4())
        case_number = f"DSP{random.randint(100000, 999999)}"
        
        # Mark transaction as disputed
        transaction.is_disputed = True
        transaction.updated_at = datetime.utcnow()
        await self.repo.update_transaction(transaction)
        
        # Simulate dispute processing time
        estimated_resolution = "5-10 business days"
        
        logger.info(f"Dispute {dispute_id} created for transaction {transaction_id}")
        return {
            "dispute_id": dispute_id,
            "transaction_id": transaction_id,
            "status": "under_review",
            "estimated_resolution": estimated_resolution,
            "case_number": case_number
        }
    
    async def get_transaction_analytics(
        self, 
        user_id: str,
        account_id: Optional[str] = None,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        Get comprehensive transaction analytics.
        
        Args:
            user_id: User identifier
            account_id: Optional account filter
            days: Analysis period in days
            
        Returns:
            Transaction analytics and insights
        """
        logger.info(f"Getting transaction analytics for user {user_id}")
        
        # Validate user exists
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        
        # Calculate period
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Get transactions
        if account_id:
            # Validate account exists and ownership
            if not await validate_account_exists(account_id, self.repo):
                raise NotFoundError(f"Account {account_id} not found")
            
            account = await self.repo.get_account_by_id(account_id)
            if account.user_id != user_id:
                raise UnauthorizedError("You don't have access to this account")
            
            transactions = await self.repo.get_account_transactions(
                account_id, 
                datetime.combine(start_date, datetime.min.time()),
                datetime.combine(end_date, datetime.max.time())
            )
        else:
            # Get all user transactions in period
            all_transactions = await self.repo.get_user_transactions(user_id)
            transactions = [
                t for t in all_transactions 
                if start_date <= t.transaction_date.date() <= end_date
            ]
        
        # Calculate analytics
        analytics = await self._calculate_comprehensive_analytics(
            transactions, start_date, end_date
        )
        analytics["account_id"] = account_id
        
        logger.info(f"Analytics calculated for {len(transactions)} transactions")
        return analytics
    
    async def export_transactions(
        self, 
        user_id: str, 
        request: TransactionExportRequest
    ) -> Dict[str, Any]:
        """
        Export transactions to various formats.
        
        Args:
            user_id: User identifier
            request: Export request
            
        Returns:
            Export job information and download link
        """
        logger.info(f"Exporting transactions for user {user_id}")
        
        # Validate user exists
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        
        # Get transactions to export
        if request.filters:
            result = await self.list_transactions(user_id, request.filters)
            transactions = result["transactions"]
        else:
            transactions = await self.repo.get_user_transactions(user_id)
        
        # Generate export
        export_id = str(uuid.uuid4())
        
        # Simulate export processing
        await asyncio.sleep(0.5)
        
        # Generate mock download URL and file info
        file_extension = request.format.lower()
        download_url = f"/api/v1/transactions/exports/{export_id}/download.{file_extension}"
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # Calculate mock file size
        record_count = len(transactions)
        estimated_size = record_count * 150  # ~150 bytes per record
        
        logger.info(f"Export {export_id} created: {record_count} records, {estimated_size} bytes")
        return {
            "export_id": export_id,
            "download_url": download_url,
            "expires_at": expires_at,
            "file_size": estimated_size,
            "record_count": record_count
        }
    
    async def get_recent_transactions(
        self, 
        user_id: str, 
        limit: int = 10,
        account_id: Optional[str] = None
    ) -> List[Transaction]:
        """
        Get most recent transactions for quick access.
        
        Args:
            user_id: User identifier
            limit: Number of transactions to return
            account_id: Optional account filter
            
        Returns:
            List of recent transactions
        """
        logger.info(f"Getting {limit} recent transactions for user {user_id}")
        
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
    
    async def get_spending_by_category(
        self, 
        user_id: str,
        account_id: Optional[str] = None,
        days: int = 30
    ) -> List[TransactionCategoryStats]:
        """
        Get spending breakdown by category.
        
        Args:
            user_id: User identifier
            account_id: Optional account filter
            days: Analysis period in days
            
        Returns:
            Category spending statistics
        """
        logger.info(f"Getting spending by category for user {user_id}")
        
        analytics = await self.get_transaction_analytics(user_id, account_id, days)
        return analytics["category_breakdown"]
    
    # Private helper methods
    async def _apply_filters(
        self, 
        transactions: List[Transaction], 
        request: TransactionListRequest
    ) -> List[Transaction]:
        """Apply filtering criteria to transactions."""
        filtered = []
        
        for transaction in transactions:
            # Account filter
            if request.account_id and transaction.account_id != request.account_id:
                continue
            
            # Transaction type filter
            if request.transaction_type and transaction.transaction_type != request.transaction_type:
                continue
            
            # Status filter
            if request.status and transaction.status != request.status:
                continue
            
            # Direction filter
            if request.direction and transaction.direction != request.direction:
                continue
            
            # Merchant category filter
            if request.merchant_category and transaction.merchant_category != request.merchant_category:
                continue
            
            # Payment method filter
            if request.payment_method and transaction.payment_method != request.payment_method:
                continue
            
            # Date range filter
            transaction_date = transaction.transaction_date.date()
            if request.start_date and transaction_date < request.start_date:
                continue
            if request.end_date and transaction_date > request.end_date:
                continue
            
            # Amount range filter
            abs_amount = abs(transaction.amount)
            if request.min_amount and abs_amount < request.min_amount:
                continue
            if request.max_amount and abs_amount > request.max_amount:
                continue
            
            # Tags filter
            if request.tags:
                if not any(tag in transaction.tags for tag in request.tags):
                    continue
            
            filtered.append(transaction)
        
        return filtered
    
    def _apply_search(self, transactions: List[Transaction], query: str) -> List[Transaction]:
        """Apply text search to transactions."""
        query_lower = query.lower()
        matching = []
        
        for transaction in transactions:
            # Search in description
            if query_lower in transaction.description.lower():
                matching.append(transaction)
                continue
            
            # Search in merchant name
            if transaction.merchant_name and query_lower in transaction.merchant_name.lower():
                matching.append(transaction)
                continue
            
            # Search in notes
            if transaction.notes and query_lower in transaction.notes.lower():
                matching.append(transaction)
                continue
            
            # Search in tags
            if any(query_lower in tag.lower() for tag in transaction.tags):
                matching.append(transaction)
                continue
        
        return matching
    
    def _sort_transactions(
        self, 
        transactions: List[Transaction], 
        sort_by: str, 
        sort_order: str
    ) -> List[Transaction]:
        """Sort transactions by specified field and order."""
        reverse = sort_order.lower() == "desc"
        
        try:
            if sort_by == "amount":
                return sorted(transactions, key=lambda x: abs(x.amount), reverse=reverse)
            elif sort_by == "merchant_name":
                return sorted(transactions, key=lambda x: x.merchant_name or "", reverse=reverse)
            elif sort_by == "category":
                return sorted(transactions, key=lambda x: x.merchant_category.value, reverse=reverse)
            else:  # Default to transaction_date
                return sorted(transactions, key=lambda x: x.transaction_date, reverse=reverse)
        except Exception as e:
            logger.warning(f"Failed to sort by {sort_by}, using default sort: {e}")
            return sorted(transactions, key=lambda x: x.transaction_date, reverse=True)
    
    def _calculate_transaction_summary(
        self, 
        transactions: List[Transaction],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> TransactionSummary:
        """Calculate summary statistics for transactions."""
        if not transactions:
            return TransactionSummary(
                period_start=start_date or date.today(),
                period_end=end_date or date.today(),
                total_transactions=0,
                total_amount=Decimal("0"),
                total_credits=Decimal("0"),
                total_debits=Decimal("0")
            )
        
        # Calculate basic stats
        total_amount = sum(abs(t.amount) for t in transactions)
        total_credits = sum(t.amount for t in transactions if t.amount > 0)
        total_debits = abs(sum(t.amount for t in transactions if t.amount < 0))
        average_transaction = total_amount / len(transactions) if transactions else Decimal("0")
        largest_transaction = max(abs(t.amount) for t in transactions) if transactions else Decimal("0")
        
        # Calculate by category
        by_category = {}
        for transaction in transactions:
            category = transaction.merchant_category.value
            amount = abs(transaction.amount)
            by_category[category] = by_category.get(category, Decimal("0")) + amount
        
        # Calculate by merchant
        by_merchant = {}
        for transaction in transactions:
            merchant = transaction.merchant_name or "Unknown"
            amount = abs(transaction.amount)
            by_merchant[merchant] = by_merchant.get(merchant, Decimal("0")) + amount
        
        # Get top 10 merchants
        top_merchants = dict(sorted(by_merchant.items(), key=lambda x: x[1], reverse=True)[:10])
        
        return TransactionSummary(
            period_start=start_date or min(t.transaction_date.date() for t in transactions),
            period_end=end_date or max(t.transaction_date.date() for t in transactions),
            total_transactions=len(transactions),
            total_amount=total_amount,
            total_credits=total_credits,
            total_debits=total_debits,
            average_transaction=average_transaction,
            largest_transaction=largest_transaction,
            by_category=by_category,
            by_merchant=top_merchants
        )
    
    async def _calculate_comprehensive_analytics(
        self, 
        transactions: List[Transaction],
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Calculate comprehensive transaction analytics."""
        
        # Category breakdown with statistics
        category_stats = {}
        total_spending = sum(abs(t.amount) for t in transactions if t.amount < 0)
        
        for category in MerchantCategory:
            category_transactions = [t for t in transactions if t.merchant_category == category and t.amount < 0]
            if category_transactions:
                total_amount = sum(abs(t.amount) for t in category_transactions)
                percentage = (total_amount / total_spending * 100) if total_spending > 0 else 0
                
                category_stats[category.value] = TransactionCategoryStats(
                    category=category,
                    transaction_count=len(category_transactions),
                    total_amount=total_amount,
                    average_amount=total_amount / len(category_transactions),
                    percentage_of_total=percentage
                )
        
        # Monthly trends
        monthly_trends = {}
        current_date = start_date
        while current_date <= end_date:
            month_key = current_date.strftime("%Y-%m")
            month_transactions = [
                t for t in transactions 
                if t.transaction_date.date().strftime("%Y-%m") == month_key and t.amount < 0
            ]
            monthly_trends[month_key] = sum(abs(t.amount) for t in month_transactions)
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        # Top merchants
        merchant_spending = {}
        for transaction in transactions:
            if transaction.amount < 0 and transaction.merchant_name:
                merchant = transaction.merchant_name
                amount = abs(transaction.amount)
                merchant_spending[merchant] = merchant_spending.get(merchant, Decimal("0")) + amount
        
        top_merchants = dict(sorted(merchant_spending.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Payment method breakdown
        payment_method_breakdown = {}
        for transaction in transactions:
            if transaction.amount < 0:
                method = transaction.payment_method.value
                amount = abs(transaction.amount)
                payment_method_breakdown[method] = payment_method_breakdown.get(method, Decimal("0")) + amount
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "total_transactions": len(transactions),
            "category_breakdown": list(category_stats.values()),
            "monthly_trends": monthly_trends,
            "top_merchants": top_merchants,
            "payment_method_breakdown": payment_method_breakdown
        }
    
    def _matches_search_query(
        self, 
        transaction: Transaction, 
        query: str, 
        search_fields: List[str], 
        fuzzy_match: bool
    ) -> bool:
        """Check if transaction matches search query."""
        query_lower = query.lower()
        
        for field in search_fields:
            field_value = ""
            
            if field == "description":
                field_value = transaction.description
            elif field == "merchant_name":
                field_value = transaction.merchant_name or ""
            elif field == "notes":
                field_value = transaction.notes or ""
            elif field == "reference_number":
                field_value = transaction.reference_number or ""
            
            field_value_lower = field_value.lower()
            
            if fuzzy_match:
                # Use fuzzy matching with similarity threshold
                similarity = SequenceMatcher(None, query_lower, field_value_lower).ratio()
                if similarity > 0.6:  # 60% similarity threshold
                    return True
            else:
                # Exact substring match
                if query_lower in field_value_lower:
                    return True
        
        return False
    
    def _generate_search_suggestions(
        self, 
        query: str, 
        transactions: List[Transaction]
    ) -> List[str]:
        """Generate search suggestions based on transaction data."""
        suggestions = set()
        query_lower = query.lower()
        
        # Extract common words from descriptions and merchant names
        for transaction in transactions[:100]:  # Limit for performance
            # From description
            words = transaction.description.lower().split()
            for word in words:
                if len(word) > 3 and query_lower in word:
                    suggestions.add(word)
            
            # From merchant name
            if transaction.merchant_name:
                merchant_words = transaction.merchant_name.lower().split()
                for word in merchant_words:
                    if len(word) > 3 and query_lower in word:
                        suggestions.add(word)
        
        # Add category suggestions
        for category in MerchantCategory:
            if query_lower in category.value.lower():
                suggestions.add(category.value.replace("_", " ").title())
        
        return sorted(list(suggestions))[:5]  # Return top 5 suggestions
    
    async def _update_similar_transactions(
        self, 
        user_id: str, 
        reference_transaction: Transaction, 
        new_category: MerchantCategory
    ) -> int:
        """Update similar transactions with the same category."""
        similar_count = 0
        
        # Get all user transactions
        all_transactions = await self.repo.get_user_transactions(user_id)
        
        for transaction in all_transactions:
            # Skip the reference transaction itself
            if transaction.transaction_id == reference_transaction.transaction_id:
                continue
            
            # Check similarity criteria
            is_similar = (
                transaction.merchant_name == reference_transaction.merchant_name or
                (transaction.description and 
                 SequenceMatcher(None, transaction.description, reference_transaction.description).ratio() > 0.8)
            )
            
            if is_similar and transaction.merchant_category != new_category:
                transaction.merchant_category = new_category
                transaction.updated_at = datetime.utcnow()
                await self.repo.update_transaction(transaction)
                similar_count += 1
        
        return similar_count


# Dependency provider
def get_transaction_service() -> TransactionService:
    """Dependency provider for transaction service."""
    return TransactionService()
