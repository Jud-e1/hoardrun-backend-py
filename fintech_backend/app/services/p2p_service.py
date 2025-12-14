"""
Peer-to-peer money transfer service for the fintech backend.
"""

import asyncio
import uuid
import random
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from urllib.parse import quote

from ..models.p2p import (
    P2PTransaction, MoneyRequest, SplitBill, PaymentLink, P2PContact,
    P2PTransactionType, P2PStatus, P2PRequestStatus, ContactMethod,
    NotificationPreference, P2PSendRequest, MoneyRequestCreateRequest,
    SplitBillCreateRequest, PaymentLinkCreateRequest, P2PQuoteRequest,
    PaymentLinkPaymentRequest
)
from ..models.base import PaginationRequest
from ..core.exceptions import NotFoundError, ValidationError, BusinessLogicError


class P2PService:
    """Service for handling peer-to-peer money operations."""
    
    def __init__(self):
        # Mock data storage - replace with actual database
        self.p2p_transactions: Dict[str, P2PTransaction] = {}
        self.money_requests: Dict[str, MoneyRequest] = {}
        self.split_bills: Dict[str, SplitBill] = {}
        self.payment_links: Dict[str, PaymentLink] = {}
        self.contacts: Dict[str, List[P2PContact]] = {}  # user_id -> contacts
        
        # Initialize with some mock data
        self._initialize_mock_data()
    
    def _initialize_mock_data(self):
        """Initialize with mock P2P data."""
        # Mock contacts for user_123
        mock_contacts = [
            P2PContact(
                contact_id="contact_001",
                user_id="user_456",
                display_name="Alice Johnson",
                contact_method=ContactMethod.EMAIL,
                contact_value="alice@example.com",
                is_registered_user=True,
                is_favorite=True,
                last_transaction_date=datetime.utcnow() - timedelta(days=2)
            ),
            P2PContact(
                contact_id="contact_002",
                user_id="user_789",
                display_name="Bob Smith",
                contact_method=ContactMethod.PHONE,
                contact_value="+1234567890",
                is_registered_user=True,
                is_favorite=False,
                last_transaction_date=datetime.utcnow() - timedelta(days=5)
            )
        ]
        self.contacts["user_123"] = mock_contacts
        
        # Mock P2P transaction
        mock_transaction = P2PTransaction(
            transaction_id="p2p_001",
            sender_user_id="user_123",
            recipient_user_id="user_456",
            recipient_contact=mock_contacts[0],
            transaction_type=P2PTransactionType.SEND_MONEY,
            status=P2PStatus.COMPLETED,
            amount=Decimal("50.00"),
            currency="USD",
            fee=Decimal("0.50"),
            total_amount=Decimal("50.50"),
            source_account_id="acc_123_001",
            destination_account_id="acc_456_001",
            message="Thanks for lunch!",
            initiated_at=datetime.utcnow() - timedelta(hours=2),
            completed_at=datetime.utcnow() - timedelta(hours=1)
        )
        self.p2p_transactions["p2p_001"] = mock_transaction
    
    async def get_contacts(self, user_id: str, search: Optional[str] = None) -> List[P2PContact]:
        """Get P2P contacts for a user."""
        await asyncio.sleep(0.1)  # Simulate database call
        
        contacts = self.contacts.get(user_id, [])
        
        if search:
            search_lower = search.lower()
            contacts = [
                contact for contact in contacts
                if (search_lower in contact.display_name.lower() or 
                    search_lower in contact.contact_value.lower())
            ]
        
        # Sort by favorites first, then by last transaction date
        contacts.sort(key=lambda x: (not x.is_favorite, x.last_transaction_date or datetime.min), reverse=True)
        
        return contacts
    
    async def add_contact(self, user_id: str, contact_value: str, contact_method: ContactMethod, 
                         display_name: str) -> P2PContact:
        """Add a new P2P contact."""
        await asyncio.sleep(0.1)
        
        # Check if contact already exists
        existing_contacts = self.contacts.get(user_id, [])
        for contact in existing_contacts:
            if contact.contact_value == contact_value and contact.contact_method == contact_method:
                raise ValidationError("Contact already exists")
        
        # Create new contact
        contact = P2PContact(
            contact_id=f"contact_{uuid.uuid4().hex[:8]}",
            user_id=f"user_{uuid.uuid4().hex[:8]}",  # Mock user ID lookup
            display_name=display_name,
            contact_method=contact_method,
            contact_value=contact_value,
            is_registered_user=random.choice([True, False]),  # Mock user lookup
            is_favorite=False
        )
        
        if user_id not in self.contacts:
            self.contacts[user_id] = []
        self.contacts[user_id].append(contact)
        
        return contact
    
    async def update_contact_favorite(self, user_id: str, contact_id: str, is_favorite: bool) -> P2PContact:
        """Update contact favorite status."""
        await asyncio.sleep(0.1)
        
        contacts = self.contacts.get(user_id, [])
        for contact in contacts:
            if contact.contact_id == contact_id:
                contact.is_favorite = is_favorite
                return contact
        
        raise NotFoundError("Contact not found")
    
    async def send_money(self, user_id: str, request: P2PSendRequest) -> P2PTransaction:
        """Send money to another user."""
        await asyncio.sleep(0.2)  # Simulate processing
        
        # Validate source account belongs to user (mock validation)
        if not request.source_account_id.startswith(f"acc_{user_id}"):
            raise ValidationError("Source account does not belong to user")
        
        # Calculate fees
        fee = await self._calculate_p2p_fee(request.amount, request.currency)
        total_amount = request.amount + fee
        
        # Find or create recipient contact
        recipient_contact = await self._find_or_create_contact(
            user_id, request.recipient_contact, request.contact_method
        )
        
        # Create P2P transaction
        transaction = P2PTransaction(
            transaction_id=f"p2p_{uuid.uuid4().hex[:8]}",
            sender_user_id=user_id,
            recipient_user_id=recipient_contact.user_id if recipient_contact.is_registered_user else None,
            recipient_contact=recipient_contact,
            transaction_type=P2PTransactionType.SEND_MONEY,
            status=P2PStatus.PENDING,
            amount=request.amount,
            currency=request.currency,
            fee=fee,
            total_amount=total_amount,
            source_account_id=request.source_account_id,
            message=request.message,
            private_note=request.private_note,
            notification_preferences=request.notification_preferences,
            requires_verification=request.amount > Decimal("1000")  # Mock risk assessment
        )
        
        self.p2p_transactions[transaction.transaction_id] = transaction
        
        # Simulate async processing
        asyncio.create_task(self._process_p2p_transaction(transaction.transaction_id))
        
        return transaction
    
    async def request_money(self, user_id: str, request: MoneyRequestCreateRequest) -> MoneyRequest:
        """Create a money request."""
        await asyncio.sleep(0.1)
        
        # Validate destination account
        if not request.destination_account_id.startswith(f"acc_{user_id}"):
            raise ValidationError("Destination account does not belong to user")
        
        # Find or create payer contact
        payer_contact = await self._find_or_create_contact(
            user_id, request.payer_contact, request.contact_method
        )
        
        # Create money request
        money_request = MoneyRequest(
            request_id=f"req_{uuid.uuid4().hex[:8]}",
            requester_user_id=user_id,
            payer_contact=payer_contact,
            payer_user_id=payer_contact.user_id if payer_contact.is_registered_user else None,
            status=P2PRequestStatus.PENDING,
            amount=request.amount,
            currency=request.currency,
            description=request.description,
            due_date=request.due_date,
            destination_account_id=request.destination_account_id,
            expires_at=datetime.utcnow() + timedelta(days=30),  # Default 30 days
            reminder_enabled=request.reminder_enabled
        )
        
        self.money_requests[money_request.request_id] = money_request
        
        # Simulate sending notification
        await self._send_money_request_notification(money_request)
        
        return money_request
    
    async def create_split_bill(self, user_id: str, request: SplitBillCreateRequest) -> SplitBill:
        """Create a split bill."""
        await asyncio.sleep(0.2)
        
        # Validate participants
        if len(request.participants) < 2:
            raise ValidationError("Split bill must have at least 2 participants")
        
        # Create split bill
        split_bill = SplitBill(
            split_bill_id=f"split_{uuid.uuid4().hex[:8]}",
            creator_user_id=user_id,
            title=request.title,
            total_amount=request.total_amount,
            currency=request.currency,
            split_type=request.split_type,
            participants=request.participants,
            bill_date=request.bill_date,
            category=request.category,
            location=request.location,
            due_date=request.due_date,
            receipt_url=request.receipt_url
        )
        
        self.split_bills[split_bill.split_bill_id] = split_bill
        
        # Create individual money requests for each participant
        requests_created = []
        for participant in request.participants:
            if participant.get("user_id") != user_id:  # Don't request from creator
                money_request = await self._create_split_request(
                    split_bill, participant, user_id
                )
                requests_created.append(money_request.request_id)
        
        split_bill.requests_created = requests_created
        
        return split_bill
    
    async def create_payment_link(self, user_id: str, request: PaymentLinkCreateRequest) -> PaymentLink:
        """Create a payment link."""
        await asyncio.sleep(0.1)
        
        # Validate destination account
        if not request.destination_account_id.startswith(f"acc_{user_id}"):
            raise ValidationError("Destination account does not belong to user")
        
        # Validate amount constraints
        if not request.is_amount_fixed:
            if request.min_amount and request.max_amount and request.min_amount > request.max_amount:
                raise ValidationError("Minimum amount cannot be greater than maximum amount")
        
        link_id = f"link_{uuid.uuid4().hex[:8]}"
        public_url = f"https://pay.hoardrun.com/p/{link_id}"
        
        payment_link = PaymentLink(
            link_id=link_id,
            user_id=user_id,
            title=request.title,
            description=request.description,
            amount=request.amount,
            currency=request.currency,
            is_amount_fixed=request.is_amount_fixed,
            min_amount=request.min_amount,
            max_amount=request.max_amount,
            destination_account_id=request.destination_account_id,
            public_url=public_url,
            expires_at=request.expires_at,
            max_uses=request.max_uses,
            require_payer_info=request.require_payer_info,
            custom_message=request.custom_message
        )
        
        self.payment_links[link_id] = payment_link
        
        return payment_link
    
    async def get_p2p_quote(self, user_id: str, request: P2PQuoteRequest) -> Dict[str, Any]:
        """Get quote for P2P transaction."""
        await asyncio.sleep(0.1)
        
        fee = await self._calculate_p2p_fee(request.amount, request.currency)
        total_cost = request.amount + fee
        
        return {
            "quote_id": f"quote_{uuid.uuid4().hex[:8]}",
            "amount": request.amount,
            "fee": fee,
            "total_cost": total_cost,
            "exchange_rate": None,  # No exchange for same currency P2P
            "delivery_time": "Instant",
            "expires_at": datetime.utcnow() + timedelta(minutes=15)
        }
    
    async def get_p2p_transactions(self, user_id: str, pagination: PaginationRequest,
                                  transaction_type: Optional[P2PTransactionType] = None,
                                  status: Optional[P2PStatus] = None) -> Dict[str, Any]:
        """Get P2P transactions for a user."""
        await asyncio.sleep(0.1)
        
        # Filter transactions for user
        user_transactions = [
            tx for tx in self.p2p_transactions.values()
            if tx.sender_user_id == user_id or tx.recipient_user_id == user_id
        ]
        
        # Apply filters
        if transaction_type:
            user_transactions = [tx for tx in user_transactions if tx.transaction_type == transaction_type]
        
        if status:
            user_transactions = [tx for tx in user_transactions if tx.status == status]
        
        # Sort by created date descending
        user_transactions.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply pagination
        total_count = len(user_transactions)
        start_idx = pagination.skip
        end_idx = start_idx + pagination.limit
        transactions = user_transactions[start_idx:end_idx]
        
        # Calculate counts
        pending_sent = len([tx for tx in user_transactions 
                           if tx.sender_user_id == user_id and tx.status == P2PStatus.PENDING])
        pending_received = len([tx for tx in user_transactions 
                               if tx.recipient_user_id == user_id and tx.status == P2PStatus.PENDING])
        
        return {
            "transactions": transactions,
            "total_count": total_count,
            "pending_sent": pending_sent,
            "pending_received": pending_received
        }
    
    async def get_p2p_transaction(self, user_id: str, transaction_id: str) -> P2PTransaction:
        """Get a specific P2P transaction."""
        await asyncio.sleep(0.1)
        
        transaction = self.p2p_transactions.get(transaction_id)
        if not transaction:
            raise NotFoundError("P2P transaction not found")
        
        # Verify user has access to this transaction
        if transaction.sender_user_id != user_id and transaction.recipient_user_id != user_id:
            raise NotFoundError("P2P transaction not found")
        
        return transaction
    
    async def cancel_p2p_transaction(self, user_id: str, transaction_id: str) -> P2PTransaction:
        """Cancel a P2P transaction."""
        await asyncio.sleep(0.1)
        
        transaction = await self.get_p2p_transaction(user_id, transaction_id)
        
        # Only sender can cancel and only if pending
        if transaction.sender_user_id != user_id:
            raise BusinessLogicError("Only sender can cancel transaction")
        
        if transaction.status not in [P2PStatus.PENDING, P2PStatus.SENT]:
            raise BusinessLogicError("Transaction cannot be cancelled in current status")
        
        transaction.status = P2PStatus.CANCELLED
        transaction.completed_at = datetime.utcnow()
        
        return transaction
    
    async def get_money_requests(self, user_id: str, pagination: PaginationRequest,
                                status: Optional[P2PRequestStatus] = None,
                                request_type: str = "all") -> Dict[str, Any]:
        """Get money requests for a user."""
        await asyncio.sleep(0.1)
        
        # Filter requests for user
        if request_type == "outgoing":
            user_requests = [req for req in self.money_requests.values() if req.requester_user_id == user_id]
        elif request_type == "incoming":
            user_requests = [req for req in self.money_requests.values() if req.payer_user_id == user_id]
        else:
            user_requests = [
                req for req in self.money_requests.values()
                if req.requester_user_id == user_id or req.payer_user_id == user_id
            ]
        
        # Apply status filter
        if status:
            user_requests = [req for req in user_requests if req.status == status]
        
        # Sort by created date descending
        user_requests.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply pagination
        total_count = len(user_requests)
        start_idx = pagination.skip
        end_idx = start_idx + pagination.limit
        requests = user_requests[start_idx:end_idx]
        
        # Calculate counts
        pending_outgoing = len([req for req in user_requests 
                               if req.requester_user_id == user_id and req.status == P2PRequestStatus.PENDING])
        pending_incoming = len([req for req in user_requests 
                               if req.payer_user_id == user_id and req.status == P2PRequestStatus.PENDING])
        
        return {
            "requests": requests,
            "total_count": total_count,
            "pending_outgoing": pending_outgoing,
            "pending_incoming": pending_incoming
        }
    
    async def get_money_request(self, user_id: str, request_id: str) -> MoneyRequest:
        """Get a specific money request."""
        await asyncio.sleep(0.1)
        
        money_request = self.money_requests.get(request_id)
        if not money_request:
            raise NotFoundError("Money request not found")
        
        # Verify user has access
        if money_request.requester_user_id != user_id and money_request.payer_user_id != user_id:
            raise NotFoundError("Money request not found")
        
        return money_request
    
    async def respond_to_money_request(self, user_id: str, request_id: str, 
                                     action: str, source_account_id: Optional[str] = None) -> MoneyRequest:
        """Respond to a money request (accept/decline)."""
        await asyncio.sleep(0.2)
        
        money_request = await self.get_money_request(user_id, request_id)
        
        # Only payer can respond
        if money_request.payer_user_id != user_id:
            raise BusinessLogicError("Only the payer can respond to this request")
        
        if money_request.status != P2PRequestStatus.PENDING:
            raise BusinessLogicError("Request cannot be modified in current status")
        
        if action == "accept":
            if not source_account_id:
                raise ValidationError("Source account required to accept request")
            
            # Create P2P transaction for payment
            send_request = P2PSendRequest(
                recipient_contact=money_request.requester_user_id,  # Use user ID directly
                contact_method=ContactMethod.USERNAME,
                amount=money_request.amount,
                currency=money_request.currency,
                source_account_id=source_account_id,
                message=f"Payment for: {money_request.description}"
            )
            
            payment_transaction = await self.send_money(user_id, send_request)
            
            # Update request
            money_request.status = P2PRequestStatus.ACCEPTED
            money_request.payments_received.append(payment_transaction.transaction_id)
            money_request.total_received = money_request.amount
            money_request.completed_at = datetime.utcnow()
            
        elif action == "decline":
            money_request.status = P2PRequestStatus.DECLINED
            money_request.completed_at = datetime.utcnow()
        
        else:
            raise ValidationError("Invalid action. Use 'accept' or 'decline'")
        
        return money_request
    
    async def cancel_money_request(self, user_id: str, request_id: str) -> MoneyRequest:
        """Cancel a money request."""
        await asyncio.sleep(0.1)
        
        money_request = await self.get_money_request(user_id, request_id)
        
        # Only requester can cancel
        if money_request.requester_user_id != user_id:
            raise BusinessLogicError("Only requester can cancel request")
        
        if money_request.status not in [P2PRequestStatus.PENDING, P2PRequestStatus.PARTIALLY_PAID]:
            raise BusinessLogicError("Request cannot be cancelled in current status")
        
        money_request.status = P2PRequestStatus.CANCELLED
        money_request.completed_at = datetime.utcnow()
        
        return money_request
    
    async def get_split_bills(self, user_id: str, pagination: PaginationRequest,
                             active_only: bool = False) -> Dict[str, Any]:
        """Get split bills for a user."""
        await asyncio.sleep(0.1)
        
        # Filter split bills for user (creator or participant)
        user_split_bills = []
        for split_bill in self.split_bills.values():
            if split_bill.creator_user_id == user_id:
                user_split_bills.append(split_bill)
            else:
                # Check if user is a participant
                for participant in split_bill.participants:
                    if participant.get("user_id") == user_id:
                        user_split_bills.append(split_bill)
                        break
        
        # Apply active filter
        if active_only:
            user_split_bills = [sb for sb in user_split_bills if not sb.is_fully_collected]
        
        # Sort by created date descending
        user_split_bills.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply pagination
        total_count = len(user_split_bills)
        start_idx = pagination.skip
        end_idx = start_idx + pagination.limit
        split_bills = user_split_bills[start_idx:end_idx]
        
        active_count = len([sb for sb in user_split_bills if not sb.is_fully_collected])
        
        return {
            "split_bills": split_bills,
            "total_count": total_count,
            "active_count": active_count
        }
    
    async def get_split_bill(self, user_id: str, split_bill_id: str) -> Dict[str, Any]:
        """Get a specific split bill with related requests."""
        await asyncio.sleep(0.1)
        
        split_bill = self.split_bills.get(split_bill_id)
        if not split_bill:
            raise NotFoundError("Split bill not found")
        
        # Verify user has access
        has_access = split_bill.creator_user_id == user_id
        if not has_access:
            for participant in split_bill.participants:
                if participant.get("user_id") == user_id:
                    has_access = True
                    break
        
        if not has_access:
            raise NotFoundError("Split bill not found")
        
        # Get related payment requests
        payment_requests = [
            self.money_requests[req_id] for req_id in split_bill.requests_created
            if req_id in self.money_requests
        ]
        
        return {
            "split_bill": split_bill,
            "payment_requests": payment_requests
        }
    
    async def get_payment_links(self, user_id: str, pagination: PaginationRequest,
                               active_only: bool = False) -> Dict[str, Any]:
        """Get payment links for a user."""
        await asyncio.sleep(0.1)
        
        # Filter payment links for user
        user_links = [link for link in self.payment_links.values() if link.user_id == user_id]
        
        # Apply active filter
        if active_only:
            user_links = [
                link for link in user_links 
                if link.is_active and not link.is_expired and not link.is_max_uses_reached
            ]
        
        # Sort by created date descending
        user_links.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply pagination
        total_count = len(user_links)
        start_idx = pagination.skip
        end_idx = start_idx + pagination.limit
        payment_links = user_links[start_idx:end_idx]
        
        active_count = len([
            link for link in user_links 
            if link.is_active and not link.is_expired and not link.is_max_uses_reached
        ])
        
        return {
            "payment_links": payment_links,
            "total_count": total_count,
            "active_count": active_count
        }
    
    async def get_payment_link(self, link_id: str) -> PaymentLink:
        """Get a payment link by ID (public access)."""
        await asyncio.sleep(0.1)
        
        payment_link = self.payment_links.get(link_id)
        if not payment_link:
            raise NotFoundError("Payment link not found")
        
        if not payment_link.is_active or payment_link.is_expired or payment_link.is_max_uses_reached:
            raise BusinessLogicError("Payment link is no longer available")
        
        return payment_link
    
    async def process_payment_link_payment(self, request: PaymentLinkPaymentRequest) -> P2PTransaction:
        """Process a payment via payment link."""
        await asyncio.sleep(0.2)
        
        payment_link = await self.get_payment_link(request.link_id)
        
        # Validate amount
        if payment_link.is_amount_fixed and payment_link.amount != request.amount:
            raise ValidationError("Amount must match the fixed amount")
        
        if not payment_link.is_amount_fixed:
            if payment_link.min_amount and request.amount < payment_link.min_amount:
                raise ValidationError("Amount below minimum")
            if payment_link.max_amount and request.amount > payment_link.max_amount:
                raise ValidationError("Amount above maximum")
        
        # Extract user ID from source account (mock extraction)
        payer_user_id = request.source_account_id.split("_")[1]
        
        # Create contact for payer
        payer_contact = P2PContact(
            contact_id=f"contact_{uuid.uuid4().hex[:8]}",
            user_id=payer_user_id,
            display_name=request.payer_name or "Anonymous",
            contact_method=ContactMethod.EMAIL,
            contact_value=request.payer_email or "unknown@example.com",
            is_registered_user=True
        )
        
        # Calculate fee
        fee = await self._calculate_p2p_fee(request.amount, payment_link.currency)
        
        # Create P2P transaction
        transaction = P2PTransaction(
            transaction_id=f"p2p_{uuid.uuid4().hex[:8]}",
            sender_user_id=payer_user_id,
            recipient_user_id=payment_link.user_id,
            recipient_contact=payer_contact,  # Reverse for payment link
            transaction_type=P2PTransactionType.PAYMENT_LINK,
            status=P2PStatus.PENDING,
            amount=request.amount,
            currency=payment_link.currency,
            fee=fee,
            total_amount=request.amount + fee,
            source_account_id=request.source_account_id,
            destination_account_id=payment_link.destination_account_id,
            message=request.payer_message
        )
        
        self.p2p_transactions[transaction.transaction_id] = transaction
        
        # Update payment link
        payment_link.current_uses += 1
        payment_link.payments_received.append(transaction.transaction_id)
        payment_link.total_received += request.amount
        
        # Simulate async processing
        asyncio.create_task(self._process_p2p_transaction(transaction.transaction_id))
        
        return transaction
    
    async def deactivate_payment_link(self, user_id: str, link_id: str) -> PaymentLink:
        """Deactivate a payment link."""
        await asyncio.sleep(0.1)
        
        payment_link = self.payment_links.get(link_id)
        if not payment_link:
            raise NotFoundError("Payment link not found")
        
        if payment_link.user_id != user_id:
            raise NotFoundError("Payment link not found")
        
        payment_link.is_active = False
        
        return payment_link
    
    async def get_p2p_analytics(self, user_id: str, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get P2P analytics for a user."""
        await asyncio.sleep(0.2)
        
        # Filter transactions in date range
        user_transactions = [
            tx for tx in self.p2p_transactions.values()
            if (tx.sender_user_id == user_id or tx.recipient_user_id == user_id) and
               start_date <= tx.created_at.date() <= end_date and
               tx.status == P2PStatus.COMPLETED
        ]
        
        # Calculate analytics
        total_sent = sum(tx.amount for tx in user_transactions if tx.sender_user_id == user_id)
        total_received = sum(tx.amount for tx in user_transactions if tx.recipient_user_id == user_id)
        transaction_count = len(user_transactions)
        average_transaction = (total_sent + total_received) / transaction_count if transaction_count > 0 else Decimal("0")
        
        # Top recipients (mock data)
        top_recipients = [
            {"name": "Alice Johnson", "amount": Decimal("250.00"), "count": 5},
            {"name": "Bob Smith", "amount": Decimal("180.50"), "count": 3}
        ]
        
        # Monthly trends (mock data)
        monthly_trends = {
            "January": Decimal("450.00"),
            "February": Decimal("380.50"),
            "March": Decimal("520.75")
        }
        
        # Popular categories (mock data)
        popular_categories = {
            "dining": 15,
            "entertainment": 8,
            "bills": 12,
            "other": 5
        }
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "total_sent": total_sent,
            "total_received": total_received,
            "transaction_count": transaction_count,
            "average_transaction": average_transaction,
            "top_recipients": top_recipients,
            "monthly_trends": monthly_trends,
            "popular_categories": popular_categories
        }
    
    async def _find_or_create_contact(self, user_id: str, contact_value: str, 
                                    contact_method: ContactMethod) -> P2PContact:
        """Find existing contact or create new one."""
        user_contacts = self.contacts.get(user_id, [])
        
        # Look for existing contact
        for contact in user_contacts:
            if contact.contact_value == contact_value and contact.contact_method == contact_method:
                return contact
        
        # Create new contact
        display_name = self._generate_display_name(contact_value, contact_method)
        return await self.add_contact(user_id, contact_value, contact_method, display_name)
    
    def _generate_display_name(self, contact_value: str, contact_method: ContactMethod) -> str:
        """Generate display name from contact value."""
        if contact_method == ContactMethod.EMAIL:
            return contact_value.split("@")[0].title()
        elif contact_method == ContactMethod.PHONE:
            return f"Contact {contact_value[-4:]}"
        elif contact_method == ContactMethod.USERNAME:
            return f"@{contact_value}"
        else:
            return "Unknown Contact"
    
    async def _calculate_p2p_fee(self, amount: Decimal, currency: str) -> Decimal:
        """Calculate P2P transaction fee."""
        # Mock fee calculation
        if amount <= Decimal("100"):
            return Decimal("0")  # Free for small amounts
        elif amount <= Decimal("1000"):
            return Decimal("0.50")  # Flat fee for medium amounts
        else:
            return amount * Decimal("0.005")  # 0.5% for large amounts
    
    async def _create_split_request(self, split_bill: SplitBill, participant: Dict[str, Any], 
                                  creator_user_id: str) -> MoneyRequest:
        """Create a money request for split bill participant."""
        # Create participant contact
        payer_contact = P2PContact(
            contact_id=f"contact_{uuid.uuid4().hex[:8]}",
            user_id=participant.get("user_id", f"user_{uuid.uuid4().hex[:8]}"),
            display_name=participant.get("name", "Unknown"),
            contact_method=ContactMethod.EMAIL,
            contact_value=participant.get("email", "unknown@example.com"),
            is_registered_user=bool(participant.get("user_id"))
        )
        
        # Create money request
        money_request = MoneyRequest(
            request_id=f"req_{uuid.uuid4().hex[:8]}",
            requester_user_id=creator_user_id,
            payer_contact=payer_contact,
            payer_user_id=participant.get("user_id"),
            status=P2PRequestStatus.PENDING,
            amount=Decimal(str(participant["amount"])),
            currency=split_bill.currency,
            description=f"Your share of: {split_bill.title}",
            due_date=split_bill.due_date,
            is_split_bill=True,
            split_bill_id=split_bill.split_bill_id,
            total_bill_amount=split_bill.total_amount,
            destination_account_id=f"acc_{creator_user_id}_001",  # Mock creator's account
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        self.money_requests[money_request.request_id] = money_request
        
        return money_request
    
    async def _process_p2p_transaction(self, transaction_id: str):
        """Simulate asynchronous P2P transaction processing."""
        await asyncio.sleep(2)  # Simulate processing delay
        
        transaction = self.p2p_transactions.get(transaction_id)
        if transaction and transaction.status == P2PStatus.PENDING:
            # Simulate success/failure
            if random.random() > 0.05:  # 95% success rate
                transaction.status = P2PStatus.COMPLETED
                transaction.completed_at = datetime.utcnow()
                
                # If recipient is registered, mark as received
                if transaction.recipient_user_id:
                    transaction.status = P2PStatus.RECEIVED
            else:
                transaction.status = P2PStatus.FAILED
                transaction.completed_at = datetime.utcnow()
    
    async def _send_money_request_notification(self, money_request: MoneyRequest):
        """Simulate sending money request notification."""
        await asyncio.sleep(0.1)
        # Mock notification sending
        print(f"Sending money request notification to {money_request.payer_contact.contact_value}")
    
    async def get_service_health(self) -> Dict[str, Any]:
        """Get P2P service health status."""
        return {
            "status": "healthy",
            "total_p2p_transactions": len(self.p2p_transactions),
            "total_money_requests": len(self.money_requests),
            "total_split_bills": len(self.split_bills),
            "total_payment_links": len(self.payment_links),
            "timestamp": datetime.utcnow()
        }
