from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum

class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_USER = "pending_user"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"

class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"

class TicketCategory(str, Enum):
    ACCOUNT_ISSUES = "account_issues"
    PAYMENT_PROBLEMS = "payment_problems"
    TRANSACTION_DISPUTES = "transaction_disputes"
    TECHNICAL_SUPPORT = "technical_support"
    FEATURE_REQUEST = "feature_request"
    BILLING_INQUIRY = "billing_inquiry"
    SECURITY_CONCERN = "security_concern"
    MOBILE_MONEY = "mobile_money"
    KYC_VERIFICATION = "kyc_verification"
    SAVINGS_GOALS = "savings_goals"
    GENERAL_INQUIRY = "general_inquiry"
    BUG_REPORT = "bug_report"

class FAQCategory(str, Enum):
    GETTING_STARTED = "getting_started"
    ACCOUNT_MANAGEMENT = "account_management"
    PAYMENTS_TRANSFERS = "payments_transfers"
    MOBILE_MONEY = "mobile_money"
    SAVINGS_INVESTMENTS = "savings_investments"
    SECURITY_PRIVACY = "security_privacy"
    FEES_CHARGES = "fees_charges"
    TROUBLESHOOTING = "troubleshooting"
    KYC_VERIFICATION = "kyc_verification"
    MARKET_DATA = "market_data"

class SupportChannelType(str, Enum):
    EMAIL = "email"
    CHAT = "chat"
    PHONE = "phone"
    IN_APP = "in_app"
    SOCIAL_MEDIA = "social_media"

# Request Models
class SupportTicketRequest(BaseModel):
    subject: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    category: TicketCategory
    priority: TicketPriority = TicketPriority.MEDIUM
    channel: SupportChannelType = SupportChannelType.IN_APP
    attachments: Optional[List[str]] = None  # File URLs or IDs
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    
    @validator('attachments')
    def validate_attachments(cls, v):
        if v and len(v) > 5:
            raise ValueError('Maximum 5 attachments allowed')
        return v

class TicketMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    attachments: Optional[List[str]] = None
    is_internal: bool = False  # Internal notes for support agents
    
    @validator('attachments')
    def validate_attachments(cls, v):
        if v and len(v) > 3:
            raise ValueError('Maximum 3 attachments allowed per message')
        return v

class TicketUpdateRequest(BaseModel):
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assigned_agent: Optional[str] = None
    internal_notes: Optional[str] = Field(None, max_length=1000)

class FAQSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)
    category: Optional[FAQCategory] = None
    limit: int = Field(10, ge=1, le=50)

class FeedbackRequest(BaseModel):
    type: str = Field(..., pattern=r'^(bug_report|feature_request|general_feedback|rating)$')
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    rating: Optional[int] = Field(None, ge=1, le=5)
    category: Optional[str] = None
    page_url: Optional[str] = None
    user_agent: Optional[str] = None

# Response Models
class SupportTicketProfile(BaseModel):
    id: str
    ticket_number: str
    subject: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    category: TicketCategory
    channel: SupportChannelType
    user_id: str
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    assigned_agent: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    first_response_at: Optional[datetime] = None
    last_activity_at: datetime
    message_count: int = 0
    attachments: List[str] = []
    tags: List[str] = []
    satisfaction_rating: Optional[int] = None

class TicketMessage(BaseModel):
    id: str
    ticket_id: str
    sender_id: str
    sender_name: str
    sender_type: str  # user, agent, system
    message: str
    attachments: List[str] = []
    is_internal: bool = False
    created_at: datetime

class TicketSummary(BaseModel):
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    closed_tickets: int
    average_resolution_time: Optional[float] = None  # in hours
    tickets_by_category: Dict[str, int]
    tickets_by_priority: Dict[str, int]
    recent_tickets: List[SupportTicketProfile]

class FAQItem(BaseModel):
    id: str
    question: str
    answer: str
    category: FAQCategory
    tags: List[str] = []
    view_count: int = 0
    helpful_count: int = 0
    not_helpful_count: int = 0
    created_at: datetime
    updated_at: datetime
    is_featured: bool = False

class FAQSearchResult(BaseModel):
    items: List[FAQItem]
    total_results: int
    search_query: str
    suggested_categories: List[str] = []

class SupportAgent(BaseModel):
    id: str
    name: str
    email: str
    specialties: List[str] = []
    is_online: bool = False
    average_rating: Optional[float] = None
    tickets_handled: int = 0
    languages: List[str] = ["en"]

class HelpArticle(BaseModel):
    id: str
    title: str
    content: str
    category: FAQCategory
    tags: List[str] = []
    author: str
    view_count: int = 0
    helpful_count: int = 0
    not_helpful_count: int = 0
    created_at: datetime
    updated_at: datetime
    is_published: bool = True
    estimated_read_time: int = 0  # in minutes

class SupportStats(BaseModel):
    total_tickets_created: int
    total_tickets_resolved: int
    average_first_response_time: float  # in hours
    average_resolution_time: float  # in hours
    customer_satisfaction_score: float  # 1-5 scale
    resolution_rate: float  # percentage
    escalation_rate: float  # percentage
    most_common_categories: List[Dict[str, Any]]
    agent_performance: List[Dict[str, Any]]

class ContactInfo(BaseModel):
    support_email: str
    support_phone: str
    business_hours: str
    emergency_contact: str
    social_media: Dict[str, str]
    office_address: str
    response_time_sla: Dict[str, str]  # by priority level

# Database Models
class SupportTicketDB(BaseModel):
    id: str
    ticket_number: str
    user_id: str
    subject: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    category: TicketCategory
    channel: SupportChannelType
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    assigned_agent: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    first_response_at: Optional[datetime] = None
    last_activity_at: datetime
    attachments: List[str] = []
    tags: List[str] = []
    satisfaction_rating: Optional[int] = None
    internal_notes: Optional[str] = None

class TicketMessageDB(BaseModel):
    id: str
    ticket_id: str
    sender_id: str
    sender_name: str
    sender_type: str
    message: str
    attachments: List[str] = []
    is_internal: bool = False
    created_at: datetime

class FAQDB(BaseModel):
    id: str
    question: str
    answer: str
    category: FAQCategory
    tags: List[str] = []
    view_count: int = 0
    helpful_count: int = 0
    not_helpful_count: int = 0
    created_at: datetime
    updated_at: datetime
    is_featured: bool = False
    is_published: bool = True

class FeedbackDB(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    description: str
    rating: Optional[int] = None
    category: Optional[str] = None
    page_url: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = "new"  # new, reviewed, implemented, rejected
    created_at: datetime
    updated_at: datetime

class HelpArticleDB(BaseModel):
    id: str
    title: str
    content: str
    category: FAQCategory
    tags: List[str] = []
    author: str
    view_count: int = 0
    helpful_count: int = 0
    not_helpful_count: int = 0
    created_at: datetime
    updated_at: datetime
    is_published: bool = True
    estimated_read_time: int = 0
