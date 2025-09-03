"""
Peer-to-peer money transfer models for the fintech backend.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from app.models.base import BaseResponse, TimestampMixin


class P2PTransactionType(str, Enum):
    """Types of P2P transactions."""
    SEND_MONEY = "send_money"
    REQUEST_MONEY = "request_money"
    SPLIT_BILL = "split_bill"
    PAYMENT_LINK = "payment_link"


class P2PStatus(str, Enum):
    """Status of P2P transactions."""
    PENDING = "pending"
    SENT = "sent"
    RECEIVED = "received"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class P2PRequestStatus(str, Enum):
    """Status of money requests."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PARTIALLY_PAID = "partially_paid"
    COMPLETED = "completed"


class ContactMethod(str, Enum):
    """Methods to contact recipients."""
    EMAIL = "email"
    PHONE = "phone"
    USERNAME = "username"
    QR_CODE = "qr_code"


class NotificationPreference(str, Enum):
    """Notification preferences for P2P transactions."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    NONE = "none"


class P2PContact(BaseModel):
    """Contact information for P2P transactions."""
    contact_id: str = Field(..., description="Unique contact identifier")
    user_id: str = Field(..., description="Contact's user ID if registered")
    display_name: str = Field(..., description="Display name")
    contact_method: ContactMethod = Field(..., description="Primary contact method")
    contact_value: str = Field(..., description="Contact value (email, phone, username)")
    avatar_url: Optional[str] = Field(None, description="Profile picture URL")
    is_registered_user: bool = Field(..., description="Whether contact is a registered user")
    is_favorite: bool = Field(default=False, description="Favorite contact for quick access")
    last_transaction_date: Optional[datetime] = Field(None, description="Last P2P transaction date")


class P2PTransaction(BaseModel, TimestampMixin):
    """P2P money transaction model."""
    transaction_id: str = Field(..., description="Unique transaction identifier")
    
    # Participants
    sender_user_id: str = Field(..., description="Sender user ID")
    recipient_user_id: Optional[str] = Field(None, description="Recipient user ID if registered")
    recipient_contact: P2PContact = Field(..., description="Recipient contact information")
    
    # Transaction details
    transaction_type: P2PTransactionType = Field(..., description="Type of P2P transaction")
    status: P2PStatus = Field(..., description="Transaction status")
    
    # Amount and currency
    amount: Decimal = Field(..., gt=0, description="Transaction amount")
    currency: str = Field(..., description="Transaction currency")
    fee: Decimal = Field(default=Decimal("0"), description="Transaction fee")
    total_amount: Decimal = Field(..., description="Total amount including fees")
    
    # Source and destination
    source_account_id: str = Field(..., description="Sender's source account")
    destination_account_id: Optional[str] = Field(None, description="Recipient's destination account")
    
    # Message and metadata
    message: Optional[str] = Field(None, description="Message to recipient")
    private_note: Optional[str] = Field(None, description="Private note for sender")
    
    # Processing information
    request_id: Optional[str] = Field(None, description="Associated request ID if applicable")
    external_reference: Optional[str] = Field(None, description="External reference number")
    
    # Timing
    initiated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(None, description="Transaction expiration time")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    
    # Notification settings
    notification_preferences: List[NotificationPreference] = Field(
        default_factory=lambda: [NotificationPreference.EMAIL, NotificationPreference.PUSH]
    )
    
    # Security and compliance
    requires_verification: bool = Field(default=False, description="Whether transaction requires additional verification")
    verification_method: Optional[str] = Field(None, description="Required verification method")
    risk_score: Optional[float] = Field(None, description="Risk assessment score")
    
    @validator('total_amount')
    def validate_total_amount(cls, v, values):
        if 'amount' in values and 'fee' in values:
            expected = values['amount'] + values['fee']
            if abs(v - expected) > Decimal("0.01"):
                raise ValueError("Total amount must equal amount plus fee")
        return v


class MoneyRequest(BaseModel, TimestampMixin):
    """Money request model for requesting payments."""
    request_id: str = Field(..., description="Unique request identifier")
    
    # Participants
    requester_user_id: str = Field(..., description="User requesting money")
    payer_contact: P2PContact = Field(..., description="Payer contact information")
    payer_user_id: Optional[str] = Field(None, description="Payer user ID if registered")
    
    # Request details
    status: P2PRequestStatus = Field(..., description="Request status")
    amount: Decimal = Field(..., gt=0, description="Requested amount")
    currency: str = Field(..., description="Request currency")
    
    # Description and purpose
    description: str = Field(..., description="What the money is for")
    due_date: Optional[date] = Field(None, description="Optional due date")
    
    # Split bill information
    is_split_bill: bool = Field(default=False, description="Whether this is a bill split")
    split_bill_id: Optional[str] = Field(None, description="Split bill group identifier")
    total_bill_amount: Optional[Decimal] = Field(None, description="Total bill amount if split")
    split_participants: List[P2PContact] = Field(default_factory=list, description="Participants in split bill")
    
    # Processing information
    destination_account_id: str = Field(..., description="Requester's account to receive money")
    
    # Timing
    expires_at: datetime = Field(..., description="Request expiration time")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    
    # Payment tracking
    payments_received: List[str] = Field(default_factory=list, description="Transaction IDs of received payments")
    total_received: Decimal = Field(default=Decimal("0"), description="Total amount received")
    
    # Reminder settings
    reminder_enabled: bool = Field(default=True, description="Send payment reminders")
    reminder_frequency: str = Field(default="daily", description="Reminder frequency")
    last_reminder_sent: Optional[datetime] = Field(None, description="Last reminder timestamp")
    
    @property
    def is_fully_paid(self) -> bool:
        """Check if request is fully paid."""
        return self.total_received >= self.amount
    
    @property
    def remaining_amount(self) -> Decimal:
        """Calculate remaining amount to be paid."""
        return max(Decimal("0"), self.amount - self.total_received)


class SplitBill(BaseModel, TimestampMixin):
    """Split bill model for dividing expenses among multiple people."""
    split_bill_id: str = Field(..., description="Unique split bill identifier")
    creator_user_id: str = Field(..., description="User who created the split")
    
    # Bill details
    title: str = Field(..., description="Bill title/description")
    total_amount: Decimal = Field(..., gt=0, description="Total bill amount")
    currency: str = Field(..., description="Bill currency")
    
    # Split configuration
    split_type: str = Field(default="equal", description="Split type (equal, custom, percentage)")
    participants: List[Dict[str, Any]] = Field(..., description="Split participants with amounts")
    
    # Metadata
    bill_date: date = Field(..., description="Date of the bill")
    category: str = Field(default="dining", description="Bill category")
    location: Optional[str] = Field(None, description="Bill location")
    receipt_url: Optional[str] = Field(None, description="Receipt image URL")
    
    # Processing
    requests_created: List[str] = Field(default_factory=list, description="Created request IDs")
    total_collected: Decimal = Field(default=Decimal("0"), description="Total amount collected")
    
    # Settings
    due_date: Optional[date] = Field(None, description="Payment due date")
    reminder_enabled: bool = Field(default=True, description="Send reminders")
    
    @property
    def is_fully_collected(self) -> bool:
        """Check if bill is fully collected."""
        return self.total_collected >= self.total_amount
    
    @property
    def collection_percentage(self) -> float:
        """Calculate collection percentage."""
        if self.total_amount > 0:
            return float(self.total_collected / self.total_amount * 100)
        return 0.0


class PaymentLink(BaseModel, TimestampMixin):
    """Payment link model for requesting payments via shareable links."""
    link_id: str = Field(..., description="Unique payment link identifier")
    user_id: str = Field(..., description="User who created the link")
    
    # Link details
    title: str = Field(..., description="Payment link title")
    description: Optional[str] = Field(None, description="Payment description")
    amount: Optional[Decimal] = Field(None, gt=0, description="Fixed amount (optional)")
    currency: str = Field(..., description="Payment currency")
    
    # Link configuration
    is_amount_fixed: bool = Field(default=True, description="Whether amount is fixed")
    min_amount: Optional[Decimal] = Field(None, description="Minimum amount if not fixed")
    max_amount: Optional[Decimal] = Field(None, description="Maximum amount if not fixed")
    
    # Destination
    destination_account_id: str = Field(..., description="Account to receive payments")
    
    # Access and security
    public_url: str = Field(..., description="Shareable payment URL")
    is_active: bool = Field(default=True, description="Whether link is active")
    expires_at: Optional[datetime] = Field(None, description="Link expiration time")
    max_uses: Optional[int] = Field(None, description="Maximum number of uses")
    current_uses: int = Field(default=0, description="Current number of uses")
    
    # Payments tracking
    payments_received: List[str] = Field(default_factory=list, description="Transaction IDs of payments")
    total_received: Decimal = Field(default=Decimal("0"), description="Total amount received")
    
    # Settings
    require_payer_info: bool = Field(default=False, description="Require payer information")
    custom_message: Optional[str] = Field(None, description="Custom thank you message")
    
    @property
    def is_expired(self) -> bool:
        """Check if payment link is expired."""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
    
    @property
    def is_max_uses_reached(self) -> bool:
        """Check if maximum uses reached."""
        if self.max_uses:
            return self.current_uses >= self.max_uses
        return False


# Request models
class P2PSendRequest(BaseModel):
    """Request model for sending money to another user."""
    recipient_contact: str = Field(..., description="Recipient contact (email, phone, username)")
    contact_method: ContactMethod = Field(..., description="Contact method type")
    amount: Decimal = Field(..., gt=0, description="Amount to send")
    currency: str = Field(default="USD", description="Currency code")
    source_account_id: str = Field(..., description="Source account ID")
    message: Optional[str] = Field(None, max_length=200, description="Message to recipient")
    private_note: Optional[str] = Field(None, max_length=200, description="Private note")
    notification_preferences: List[NotificationPreference] = Field(
        default_factory=lambda: [NotificationPreference.EMAIL, NotificationPreference.PUSH]
    )


class MoneyRequestCreateRequest(BaseModel):
    """Request model for requesting money from another user."""
    payer_contact: str = Field(..., description="Payer contact (email, phone, username)")
    contact_method: ContactMethod = Field(..., description="Contact method type")
    amount: Decimal = Field(..., gt=0, description="Amount to request")
    currency: str = Field(default="USD", description="Currency code")
    destination_account_id: str = Field(..., description="Account to receive money")
    description: str = Field(..., min_length=1, max_length=200, description="What the money is for")
    due_date: Optional[date] = Field(None, description="Optional due date")
    reminder_enabled: bool = Field(default=True, description="Enable payment reminders")


class SplitBillCreateRequest(BaseModel):
    """Request model for creating a split bill."""
    title: str = Field(..., min_length=1, max_length=100, description="Bill title")
    total_amount: Decimal = Field(..., gt=0, description="Total bill amount")
    currency: str = Field(default="USD", description="Bill currency")
    participants: List[Dict[str, Any]] = Field(..., min_items=1, description="Bill participants")
    split_type: str = Field(default="equal", description="Split type")
    bill_date: date = Field(default_factory=date.today, description="Bill date")
    category: str = Field(default="dining", description="Bill category")
    location: Optional[str] = Field(None, description="Bill location")
    due_date: Optional[date] = Field(None, description="Payment due date")
    receipt_url: Optional[str] = Field(None, description="Receipt image URL")


class PaymentLinkCreateRequest(BaseModel):
    """Request model for creating payment links."""
    title: str = Field(..., min_length=1, max_length=100, description="Payment link title")
    description: Optional[str] = Field(None, max_length=500, description="Payment description")
    amount: Optional[Decimal] = Field(None, gt=0, description="Fixed amount")
    currency: str = Field(default="USD", description="Payment currency")
    destination_account_id: str = Field(..., description="Account to receive payments")
    is_amount_fixed: bool = Field(default=True, description="Whether amount is fixed")
    min_amount: Optional[Decimal] = Field(None, gt=0, description="Minimum amount if not fixed")
    max_amount: Optional[Decimal] = Field(None, gt=0, description="Maximum amount if not fixed")
    expires_at: Optional[datetime] = Field(None, description="Link expiration time")
    max_uses: Optional[int] = Field(None, gt=0, description="Maximum number of uses")
    require_payer_info: bool = Field(default=False, description="Require payer information")
    custom_message: Optional[str] = Field(None, max_length=200, description="Custom thank you message")


class P2PQuoteRequest(BaseModel):
    """Request model for P2P transaction quotes."""
    amount: Decimal = Field(..., gt=0, description="Transaction amount")
    currency: str = Field(..., description="Transaction currency")
    transaction_type: P2PTransactionType = Field(..., description="Type of P2P transaction")
    recipient_country: Optional[str] = Field(None, description="Recipient country for international fees")


class PaymentLinkPaymentRequest(BaseModel):
    """Request model for making a payment via payment link."""
    link_id: str = Field(..., description="Payment link ID")
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    payer_name: Optional[str] = Field(None, description="Payer name")
    payer_email: Optional[str] = Field(None, description="Payer email")
    payer_message: Optional[str] = Field(None, max_length=200, description="Message from payer")
    source_account_id: str = Field(..., description="Payer's source account")


# Response models
class P2PContactListResponse(BaseResponse):
    """Response model for P2P contact listing."""
    contacts: List[P2PContact] = Field(..., description="List of P2P contacts")
    total_count: int = Field(..., description="Total number of contacts")
    recent_contacts: List[P2PContact] = Field(..., description="Recently used contacts")
    favorites: List[P2PContact] = Field(..., description="Favorite contacts")


class P2PTransactionResponse(BaseResponse):
    """Response model for P2P transaction operations."""
    transaction: P2PTransaction = Field(..., description="P2P transaction details")


class P2PTransactionListResponse(BaseResponse):
    """Response model for P2P transaction listing."""
    transactions: List[P2PTransaction] = Field(..., description="List of P2P transactions")
    total_count: int = Field(..., description="Total number of transactions")
    pending_sent: int = Field(..., description="Number of pending sent transactions")
    pending_received: int = Field(..., description="Number of pending received transactions")


class MoneyRequestResponse(BaseResponse):
    """Response model for money request operations."""
    request: MoneyRequest = Field(..., description="Money request details")


class MoneyRequestListResponse(BaseResponse):
    """Response model for money request listing."""
    requests: List[MoneyRequest] = Field(..., description="List of money requests")
    total_count: int = Field(..., description="Total number of requests")
    pending_outgoing: int = Field(..., description="Number of pending outgoing requests")
    pending_incoming: int = Field(..., description="Number of pending incoming requests")


class SplitBillResponse(BaseResponse):
    """Response model for split bill operations."""
    split_bill: SplitBill = Field(..., description="Split bill details")
    payment_requests: List[MoneyRequest] = Field(..., description="Individual payment requests")


class SplitBillListResponse(BaseResponse):
    """Response model for split bill listing."""
    split_bills: List[SplitBill] = Field(..., description="List of split bills")
    total_count: int = Field(..., description="Total number of split bills")
    active_count: int = Field(..., description="Number of active split bills")


class PaymentLinkResponse(BaseResponse):
    """Response model for payment link operations."""
    payment_link: PaymentLink = Field(..., description="Payment link details")


class PaymentLinkListResponse(BaseResponse):
    """Response model for payment link listing."""
    payment_links: List[PaymentLink] = Field(..., description="List of payment links")
    total_count: int = Field(..., description="Total number of payment links")
    active_count: int = Field(..., description="Number of active payment links")


class P2PQuoteResponse(BaseResponse):
    """Response model for P2P quotes."""
    quote_id: str = Field(..., description="Quote identifier")
    amount: Decimal = Field(..., description="Transaction amount")
    fee: Decimal = Field(..., description="Transaction fee")
    total_cost: Decimal = Field(..., description="Total cost")
    exchange_rate: Optional[Decimal] = Field(None, description="Exchange rate if applicable")
    delivery_time: str = Field(..., description="Estimated delivery time")
    expires_at: datetime = Field(..., description="Quote expiration time")


class P2PAnalyticsResponse(BaseResponse):
    """Response model for P2P analytics."""
    period_start: date = Field(..., description="Analysis period start")
    period_end: date = Field(..., description="Analysis period end")
    total_sent: Decimal = Field(..., description="Total amount sent")
    total_received: Decimal = Field(..., description="Total amount received")
    transaction_count: int = Field(..., description="Total number of transactions")
    average_transaction: Decimal = Field(..., description="Average transaction amount")
    top_recipients: List[Dict[str, Any]] = Field(..., description="Top recipients by amount")
    monthly_trends: Dict[str, Decimal] = Field(..., description="Monthly P2P trends")
    popular_categories: Dict[str, int] = Field(..., description="Popular transaction categories")
