"""
Card management service for the fintech backend.
"""

import uuid
import random
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Optional, Dict, Any
import asyncio

from app.models.card import (
    Card, CardType, CardStatus, CardNetwork, CardLimit, CardDetails,
    TransactionType, LimitPeriod, CardCreateRequest, CardUpdateRequest,
    CardStatusRequest, CardLimitRequest, CardPinChangeRequest,
    CardTransactionSummary
)
from app.core.exceptions import (
    ValidationError, NotFoundError, BusinessLogicError, 
    InsufficientFundsError, UnauthorizedError
)
from app.data.repository import get_repository_manager
from app.utils.validation import validate_account_exists, validate_user_exists
from app.utils.calculations import calculate_fee
from app.config.logging import get_logger
from app.external.payment_gateway import get_payment_gateway

logger = get_logger(__name__)


class CardService:
    """Service for managing payment cards and related operations."""
    
    def __init__(self):
        self.repo = get_repository_manager()
        self.payment_gateway = get_payment_gateway()
    
    async def list_user_cards(
        self, 
        user_id: str, 
        card_type: Optional[CardType] = None,
        status: Optional[CardStatus] = None,
        account_id: Optional[str] = None
    ) -> List[Card]:
        """
        List all cards for a user with optional filtering.
        
        Args:
            user_id: User identifier
            card_type: Optional card type filter
            status: Optional status filter
            account_id: Optional account filter
            
        Returns:
            List of user cards
        """
        logger.info(f"Listing cards for user {user_id}")
        
        # Validate user exists
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        
        # Get all user cards
        all_cards = await self.repo.get_user_cards(user_id)
        
        # Apply filters
        filtered_cards = []
        for card in all_cards:
            if card_type and card.card_type != card_type:
                continue
            if status and card.status != status:
                continue
            if account_id and card.account_id != account_id:
                continue
            filtered_cards.append(card)
        
        logger.info(f"Found {len(filtered_cards)} cards for user {user_id}")
        return filtered_cards
    
    async def get_card_details(self, card_id: str, user_id: str) -> Card:
        """
        Get detailed information for a specific card.
        
        Args:
            card_id: Card identifier
            user_id: User identifier
            
        Returns:
            Card details
        """
        logger.info(f"Getting card details for {card_id}")
        
        card = await self.repo.get_card_by_id(card_id)
        if not card:
            raise NotFoundError(f"Card {card_id} not found")
        
        # Verify ownership
        if card.user_id != user_id:
            raise UnauthorizedError("You don't have access to this card")
        
        return card
    
    async def create_card(
        self, 
        user_id: str, 
        request: CardCreateRequest
    ) -> Dict[str, Any]:
        """
        Create a new payment card.
        
        Args:
            user_id: User identifier
            request: Card creation request
            
        Returns:
            Created card and delivery information
        """
        logger.info(f"Creating new card for user {user_id}")
        
        # Validate user and account
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        
        if not await validate_account_exists(request.account_id, self.repo):
            raise NotFoundError(f"Account {request.account_id} not found")
        
        # Verify account ownership
        account = await self.repo.get_account_by_id(request.account_id)
        if account.user_id != user_id:
            raise UnauthorizedError("You don't have access to this account")
        
        # Check if user already has maximum cards
        existing_cards = await self.repo.get_user_cards(user_id)
        if len(existing_cards) >= 10:  # Business rule: max 10 cards per user
            raise BusinessLogicError("Maximum number of cards reached (10)")
        
        # Generate card details
        card_id = str(uuid.uuid4())
        masked_number = self._generate_masked_card_number(request.card_network)
        expiry_month = random.randint(1, 12)
        expiry_year = datetime.now().year + random.randint(3, 7)
        
        # Create default limits
        default_limits = self._create_default_limits(request.card_type)
        
        # Create card
        card = Card(
            card_id=card_id,
            user_id=user_id,
            account_id=request.account_id,
            card_type=request.card_type,
            card_network=request.card_network,
            status=CardStatus.ACTIVE,
            masked_number=masked_number,
            card_name=request.card_name,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            limits=default_limits,
            is_contactless_enabled=request.is_contactless_enabled,
            is_online_enabled=request.is_online_enabled,
            is_international_enabled=request.is_international_enabled,
            pin_attempts_remaining=3,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )\
        
        # Save card
        await self.repo.create_card(card)
        
        # Simulate card processing with payment gateway
        await self.payment_gateway.validate_payment_method({
            "card_number": masked_number,
            "expiry_month": expiry_month,
            "expiry_year": expiry_year,
            "card_type": request.card_type.value
        })
        
        delivery_estimate = self._calculate_delivery_estimate(request.card_type)
        
        logger.info(f"Card {card_id} created successfully for user {user_id}")
        return {
            "card": card,
            "delivery_estimate": delivery_estimate
        }
    
    async def update_card_settings(
        self, 
        card_id: str, 
        user_id: str, 
        request: CardUpdateRequest
    ) -> Card:
        """
        Update card settings and preferences.
        
        Args:
            card_id: Card identifier
            user_id: User identifier
            request: Update request
            
        Returns:
            Updated card
        """
        logger.info(f"Updating card settings for {card_id}")
        
        card = await self.get_card_details(card_id, user_id)
        
        # Check if card can be updated
        if card.status in [CardStatus.CANCELLED, CardStatus.EXPIRED]:
            raise BusinessLogicError("Cannot update cancelled or expired card")
        
        # Update fields
        if request.card_name is not None:
            card.card_name = request.card_name
        if request.is_contactless_enabled is not None:
            card.is_contactless_enabled = request.is_contactless_enabled
        if request.is_online_enabled is not None:
            card.is_online_enabled = request.is_online_enabled
        if request.is_international_enabled is not None:
            card.is_international_enabled = request.is_international_enabled
        
        card.updated_at = datetime.utcnow()
        
        # Save updated card
        await self.repo.update_card(card)
        
        logger.info(f"Card {card_id} settings updated successfully")
        return card
    
    async def change_card_status(
        self, 
        card_id: str, 
        user_id: str, 
        request: CardStatusRequest
    ) -> Card:
        """
        Change card status (freeze, unfreeze, block, etc.).
        
        Args:
            card_id: Card identifier
            user_id: User identifier
            request: Status change request
            
        Returns:
            Updated card
        """
        logger.info(f"Changing card {card_id} status to {request.status}")
        
        card = await self.get_card_details(card_id, user_id)
        
        # Validate status transition
        if not self._is_valid_status_transition(card.status, request.status):
            raise BusinessLogicError(
                f"Cannot change card status from {card.status} to {request.status}"
            )
        
        # Update status
        old_status = card.status
        card.status = request.status
        card.updated_at = datetime.utcnow()
        
        # Reset PIN attempts if unblocking
        if old_status == CardStatus.BLOCKED and request.status == CardStatus.ACTIVE:
            card.pin_attempts_remaining = 3
        
        # Save updated card
        await self.repo.update_card(card)
        
        logger.info(f"Card {card_id} status changed from {old_status} to {request.status}")
        return card
    
    async def set_card_limit(
        self, 
        card_id: str, 
        user_id: str, 
        request: CardLimitRequest
    ) -> List[CardLimit]:
        """
        Set or update a card spending limit.
        
        Args:
            card_id: Card identifier
            user_id: User identifier
            request: Limit setting request
            
        Returns:
            Updated card limits
        """
        logger.info(f"Setting limit for card {card_id}: {request.transaction_type} {request.period}")
        
        card = await self.get_card_details(card_id, user_id)
        
        if card.status != CardStatus.ACTIVE:
            raise BusinessLogicError("Cannot set limits on inactive card")
        
        # Find existing limit for this transaction type and period
        existing_limit_index = None
        for i, limit in enumerate(card.limits):
            if (limit.transaction_type == request.transaction_type and 
                limit.period == request.period):
                existing_limit_index = i
                break
        
        # Calculate period dates
        now = datetime.utcnow()
        period_start, period_end = self._calculate_period_dates(now, request.period)
        
        # Create new limit
        new_limit = CardLimit(
            transaction_type=request.transaction_type,
            period=request.period,
            limit_amount=request.limit_amount,
            current_usage=Decimal("0"),  # Reset usage for new limit
            period_start=period_start,
            period_end=period_end,
            is_enabled=request.is_enabled
        )
        
        # Update or add limit
        if existing_limit_index is not None:
            # Preserve current usage if within the same period
            old_limit = card.limits[existing_limit_index]
            if (old_limit.period_start <= now <= old_limit.period_end):
                new_limit.current_usage = old_limit.current_usage
            card.limits[existing_limit_index] = new_limit
        else:
            card.limits.append(new_limit)
        
        card.updated_at = datetime.utcnow()
        await self.repo.update_card(card)
        
        logger.info(f"Limit set successfully for card {card_id}")
        return card.limits
    
    async def change_pin(
        self, 
        card_id: str, 
        user_id: str, 
        request: CardPinChangeRequest
    ) -> bool:
        """
        Change card PIN.
        
        Args:
            card_id: Card identifier
            user_id: User identifier
            request: PIN change request
            
        Returns:
            Success status
        """
        logger.info(f"Changing PIN for card {card_id}")
        
        card = await self.get_card_details(card_id, user_id)
        
        if card.status != CardStatus.ACTIVE:
            raise BusinessLogicError("Cannot change PIN for inactive card")
        
        if card.pin_attempts_remaining <= 0:
            raise BusinessLogicError("Card is blocked due to too many failed PIN attempts")
        
        # In a real implementation, we would verify the current PIN
        # For this mock, we'll simulate PIN verification
        await asyncio.sleep(0.1)  # Simulate processing time
        
        # Simulate PIN validation (90% success rate)
        if random.random() < 0.1:
            card.pin_attempts_remaining -= 1
            if card.pin_attempts_remaining <= 0:
                card.status = CardStatus.BLOCKED
            await self.repo.update_card(card)
            raise UnauthorizedError("Current PIN is incorrect")
        
        # Reset PIN attempts and update timestamp
        card.pin_attempts_remaining = 3
        card.updated_at = datetime.utcnow()
        await self.repo.update_card(card)
        
        logger.info(f"PIN changed successfully for card {card_id}")
        return True
    
    async def get_card_limits(self, card_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get card spending limits and usage.
        
        Args:
            card_id: Card identifier
            user_id: User identifier
            
        Returns:
            Card limits and remaining amounts
        """
        logger.info(f"Getting limits for card {card_id}")
        
        card = await self.get_card_details(card_id, user_id)
        
        # Update limit periods and usage
        updated_limits = []
        for limit in card.limits:
            updated_limit = await self._update_limit_period(limit, card_id)
            updated_limits.append(updated_limit)
        
        card.limits = updated_limits
        await self.repo.update_card(card)
        
        return {
            "limits": card.limits,
            "remaining_limits": card.remaining_limit
        }
    
    async def get_card_usage_analytics(
        self, 
        card_id: str, 
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get card usage analytics and spending patterns.
        
        Args:
            card_id: Card identifier
            user_id: User identifier
            days: Number of days to analyze
            
        Returns:
            Card usage analytics
        """
        logger.info(f"Getting usage analytics for card {card_id}")
        
        card = await self.get_card_details(card_id, user_id)
        
        # Calculate period
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get card transactions
        transactions = await self.repo.get_card_transactions(
            card_id, start_date, end_date
        )
        
        # Calculate transaction summaries
        transaction_summaries = self._calculate_transaction_summaries(transactions)
        
        # Calculate merchant categories
        merchant_categories = self._calculate_merchant_categories(transactions)
        
        # Calculate total spent
        total_spent = sum(t.amount for t in transactions if t.amount > 0)
        
        return {
            "card_id": card_id,
            "period_start": start_date,
            "period_end": end_date,
            "transaction_summary": transaction_summaries,
            "total_spent": total_spent,
            "merchant_categories": merchant_categories
        }
    
    async def freeze_card(self, card_id: str, user_id: str, reason: str = "User requested") -> Card:
        """
        Freeze a card to prevent transactions.
        
        Args:
            card_id: Card identifier
            user_id: User identifier
            reason: Reason for freezing
            
        Returns:
            Updated card
        """
        return await self.change_card_status(
            card_id, 
            user_id, 
            CardStatusRequest(status=CardStatus.FROZEN, reason=reason)
        )
    
    async def unfreeze_card(self, card_id: str, user_id: str, reason: str = "User requested") -> Card:
        """
        Unfreeze a card to allow transactions.
        
        Args:
            card_id: Card identifier
            user_id: User identifier
            reason: Reason for unfreezing
            
        Returns:
            Updated card
        """
        return await self.change_card_status(
            card_id, 
            user_id, 
            CardStatusRequest(status=CardStatus.ACTIVE, reason=reason)
        )
    
    async def block_card(self, card_id: str, user_id: str, reason: str = "Security concern") -> Card:
        """
        Block a card due to security concerns.
        
        Args:
            card_id: Card identifier
            user_id: User identifier
            reason: Reason for blocking
            
        Returns:
            Updated card
        """
        return await self.change_card_status(
            card_id, 
            user_id, 
            CardStatusRequest(status=CardStatus.BLOCKED, reason=reason)
        )
    
    async def cancel_card(self, card_id: str, user_id: str, reason: str = "User requested") -> Card:
        """
        Cancel a card permanently.
        
        Args:
            card_id: Card identifier
            user_id: User identifier
            reason: Reason for cancellation
            
        Returns:
            Updated card
        """
        return await self.change_card_status(
            card_id, 
            user_id, 
            CardStatusRequest(status=CardStatus.CANCELLED, reason=reason)
        )
    
    def _generate_masked_card_number(self, network: CardNetwork) -> str:
        """Generate a masked card number based on network."""
        prefixes = {
            CardNetwork.VISA: "4",
            CardNetwork.MASTERCARD: "5",
            CardNetwork.AMEX: "3",
            CardNetwork.DISCOVER: "6"
        }
        
        prefix = prefixes.get(network, "4")
        last_four = f"{random.randint(1000, 9999)}"
        
        return f"{prefix}*** **** **** {last_four}"
    
    def _create_default_limits(self, card_type: CardType) -> List[CardLimit]:
        """Create default spending limits based on card type."""
        now = datetime.utcnow()
        
        # Default limits vary by card type
        default_amounts = {
            CardType.DEBIT: {
                (TransactionType.ATM_WITHDRAWAL, LimitPeriod.DAILY): Decimal("1000"),
                (TransactionType.POS_PURCHASE, LimitPeriod.DAILY): Decimal("5000"),
                (TransactionType.ONLINE_PURCHASE, LimitPeriod.DAILY): Decimal("3000"),
                (TransactionType.CONTACTLESS, LimitPeriod.DAILY): Decimal("500"),
                (TransactionType.INTERNATIONAL, LimitPeriod.MONTHLY): Decimal("10000"),
            },
            CardType.CREDIT: {
                (TransactionType.POS_PURCHASE, LimitPeriod.MONTHLY): Decimal("50000"),
                (TransactionType.ONLINE_PURCHASE, LimitPeriod.MONTHLY): Decimal("30000"),
                (TransactionType.CONTACTLESS, LimitPeriod.DAILY): Decimal("1000"),
                (TransactionType.INTERNATIONAL, LimitPeriod.MONTHLY): Decimal("25000"),
            },
            CardType.PREPAID: {
                (TransactionType.ATM_WITHDRAWAL, LimitPeriod.DAILY): Decimal("500"),
                (TransactionType.POS_PURCHASE, LimitPeriod.DAILY): Decimal("2000"),
                (TransactionType.ONLINE_PURCHASE, LimitPeriod.DAILY): Decimal("1500"),
                (TransactionType.CONTACTLESS, LimitPeriod.DAILY): Decimal("300"),
            }
        }
        
        limits = []
        for (tx_type, period), amount in default_amounts.get(card_type, {}).items():
            period_start, period_end = self._calculate_period_dates(now, period)
            
            limits.append(CardLimit(
                transaction_type=tx_type,
                period=period,
                limit_amount=amount,
                current_usage=Decimal("0"),
                period_start=period_start,
                period_end=period_end,
                is_enabled=True
            ))
        
        return limits
    
    def _calculate_period_dates(self, reference_date: datetime, period: LimitPeriod) -> tuple:
        """Calculate start and end dates for a limit period."""
        if period == LimitPeriod.DAILY:
            start = reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1) - timedelta(microseconds=1)
        elif period == LimitPeriod.WEEKLY:
            # Start of week (Monday)
            days_since_monday = reference_date.weekday()
            start = (reference_date - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end = start + timedelta(weeks=1) - timedelta(microseconds=1)
        else:  # MONTHLY
            start = reference_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Calculate next month
            if start.month == 12:
                next_month = start.replace(year=start.year + 1, month=1)
            else:
                next_month = start.replace(month=start.month + 1)
            end = next_month - timedelta(microseconds=1)
        
        return start, end
    
    def _is_valid_status_transition(self, current: CardStatus, new: CardStatus) -> bool:
        """Check if a status transition is valid."""
        valid_transitions = {
            CardStatus.ACTIVE: [CardStatus.FROZEN, CardStatus.BLOCKED, CardStatus.CANCELLED],
            CardStatus.FROZEN: [CardStatus.ACTIVE, CardStatus.CANCELLED],
            CardStatus.BLOCKED: [CardStatus.ACTIVE, CardStatus.CANCELLED],
            CardStatus.EXPIRED: [CardStatus.CANCELLED],
            CardStatus.CANCELLED: []  # No transitions from cancelled
        }
        
        return new in valid_transitions.get(current, [])
    
    async def _update_limit_period(self, limit: CardLimit, card_id: str) -> CardLimit:
        """Update limit period if it has expired."""
        now = datetime.utcnow()
        
        if now > limit.period_end:
            # Period has expired, reset usage and update period
            new_start, new_end = self._calculate_period_dates(now, limit.period)
            limit.period_start = new_start
            limit.period_end = new_end
            limit.current_usage = Decimal("0")
            
            logger.info(f"Reset limit period for card {card_id} - {limit.transaction_type}")
        
        return limit
    
    def _calculate_transaction_summaries(self, transactions) -> List[CardTransactionSummary]:
        """Calculate transaction summaries by type."""
        # Group transactions by type
        by_type = {}
        for transaction in transactions:
            tx_type = getattr(transaction, 'transaction_type', 'pos_purchase')
            if tx_type not in by_type:
                by_type[tx_type] = []
            by_type[tx_type].append(transaction)
        
        summaries = []
        for tx_type, txs in by_type.items():
            if not txs:
                continue
                
            total_amount = sum(tx.amount for tx in txs if tx.amount > 0)
            count = len(txs)
            average = total_amount / count if count > 0 else Decimal("0")
            
            summaries.append(CardTransactionSummary(
                transaction_type=tx_type,
                period=LimitPeriod.MONTHLY,  # For analytics
                transaction_count=count,
                total_amount=total_amount,
                average_amount=average
            ))
        
        return summaries
    
    def _calculate_merchant_categories(self, transactions) -> Dict[str, Decimal]:
        """Calculate spending by merchant category."""
        categories = {}
        for transaction in transactions:
            category = getattr(transaction, 'category', 'Other')
            amount = transaction.amount if transaction.amount > 0 else Decimal("0")
            categories[category] = categories.get(category, Decimal("0")) + amount
        
        return categories
    
    def _calculate_delivery_estimate(self, card_type: CardType) -> str:
        """Calculate estimated delivery time for new card."""
        estimates = {
            CardType.DEBIT: "5-7 business days",
            CardType.CREDIT: "7-10 business days",
            CardType.PREPAID: "3-5 business days"
        }
        return estimates.get(card_type, "5-7 business days")


# Dependency provider
def get_card_service() -> CardService:
    """Dependency provider for card service."""
    return CardService()
