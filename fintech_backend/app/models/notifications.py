from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum

class NotificationType(str, Enum):
    TRANSACTION = "transaction"
    SECURITY = "security"
    ACCOUNT = "account"
    PAYMENT = "payment"
    SAVINGS = "savings"
    KYC = "kyc"
    SYSTEM = "system"
    MARKETING = "marketing"
    REMINDER = "reminder"

class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class NotificationStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"

class NotificationChannel(str, Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"

# Request Models
class NotificationCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)
    type: NotificationType
    priority: NotificationPriority = NotificationPriority.MEDIUM
    channels: List[NotificationChannel] = [NotificationChannel.IN_APP]
    metadata: Optional[Dict[str, Any]] = None
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    @validator('channels')
    def validate_channels(cls, v):
        if not v:
            raise ValueError('At least one notification channel must be specified')
        return v

class NotificationUpdateRequest(BaseModel):
    status: Optional[NotificationStatus] = None
    read_at: Optional[datetime] = None

class BulkNotificationUpdateRequest(BaseModel):
    notification_ids: List[str] = Field(..., min_items=1, max_items=100)
    status: NotificationStatus
    
    @validator('notification_ids')
    def validate_notification_ids(cls, v):
        if len(set(v)) != len(v):
            raise ValueError('Duplicate notification IDs are not allowed')
        return v

class NotificationPreferencesRequest(BaseModel):
    transaction_notifications: bool = True
    security_notifications: bool = True
    account_notifications: bool = True
    payment_notifications: bool = True
    savings_notifications: bool = True
    kyc_notifications: bool = True
    system_notifications: bool = True
    marketing_notifications: bool = False
    reminder_notifications: bool = True
    
    email_enabled: bool = True
    sms_enabled: bool = True
    push_enabled: bool = True
    
    quiet_hours_start: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    quiet_hours_end: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    timezone: str = "UTC"

class NotificationFilters(BaseModel):
    type: Optional[NotificationType] = None
    status: Optional[NotificationStatus] = None
    priority: Optional[NotificationPriority] = None
    channel: Optional[NotificationChannel] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    unread_only: bool = False

# Response Models
class NotificationProfile(BaseModel):
    id: str
    title: str
    message: str
    type: NotificationType
    priority: NotificationPriority
    status: NotificationStatus
    channels: List[NotificationChannel]
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    read_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_expired: bool = False

class NotificationSummary(BaseModel):
    total_notifications: int
    unread_count: int
    read_count: int
    archived_count: int
    by_type: Dict[str, int]
    by_priority: Dict[str, int]
    recent_notifications: List[NotificationProfile]

class NotificationPreferencesProfile(BaseModel):
    user_id: str
    transaction_notifications: bool
    security_notifications: bool
    account_notifications: bool
    payment_notifications: bool
    savings_notifications: bool
    kyc_notifications: bool
    system_notifications: bool
    marketing_notifications: bool
    reminder_notifications: bool
    
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    timezone: str
    updated_at: datetime

class NotificationDeliveryStatus(BaseModel):
    notification_id: str
    channel: NotificationChannel
    status: str  # sent, delivered, failed, pending
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None

class NotificationStats(BaseModel):
    total_sent: int
    total_delivered: int
    total_failed: int
    delivery_rate: float
    by_channel: Dict[str, Dict[str, int]]
    by_type: Dict[str, Dict[str, int]]
    recent_activity: List[Dict[str, Any]]

# Database Models
class NotificationDB(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    type: NotificationType
    priority: NotificationPriority
    status: NotificationStatus
    channels: List[NotificationChannel]
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    read_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    updated_at: datetime

class NotificationPreferencesDB(BaseModel):
    id: str
    user_id: str
    transaction_notifications: bool
    security_notifications: bool
    account_notifications: bool
    payment_notifications: bool
    savings_notifications: bool
    kyc_notifications: bool
    system_notifications: bool
    marketing_notifications: bool
    reminder_notifications: bool
    
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    timezone: str
    created_at: datetime
    updated_at: datetime

class NotificationDeliveryDB(BaseModel):
    id: str
    notification_id: str
    user_id: str
    channel: NotificationChannel
    status: str
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    attempts: int = 0
    created_at: datetime
    updated_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Smart / AI-driven notification models (merged from smart_notifications.py)
# SmartNotification is a Notification with optional smart_metadata.
# ─────────────────────────────────────────────────────────────────────────────
from decimal import Decimal


class SmartNotificationType(str, Enum):
    """Types of smart notifications (decision nudges)."""
    SURPLUS_DETECTED = "surplus_detected"
    INVESTMENT_OPPORTUNITY = "investment_opportunity"
    OVERSPENDING_WARNING = "overspending_warning"
    GOAL_PROGRESS_NUDGE = "goal_progress_nudge"
    SAVINGS_OPPORTUNITY = "savings_opportunity"
    BUDGET_ALERT = "budget_alert"
    EXPENSE_REDUCTION = "expense_reduction"
    INCOME_OPTIMIZATION = "income_optimization"
    DEBT_PAYOFF_SUGGESTION = "debt_payoff_suggestion"
    EMERGENCY_FUND_REMINDER = "emergency_fund_reminder"


class NudgeAction(str, Enum):
    """Recommended actions for nudges."""
    SAVE_NOW = "save_now"
    INVEST_NOW = "invest_now"
    REDUCE_SPENDING = "reduce_spending"
    REVIEW_BUDGET = "review_budget"
    SET_GOAL = "set_goal"
    INCREASE_CONTRIBUTION = "increase_contribution"
    PAUSE_SPENDING = "pause_spending"
    REVIEW_SUBSCRIPTIONS = "review_subscriptions"


class SmartMetadata(BaseModel):
    """Optional smart metadata attached to any notification."""
    smart_type: SmartNotificationType
    recommended_action: NudgeAction
    action_details: Dict[str, Any] = {}
    amount: Optional[Decimal] = None
    category: Optional[str] = None
    goal_id: Optional[str] = None
    budget_id: Optional[str] = None
    is_acted_upon: bool = False
    action_taken_at: Optional[datetime] = None
    confidence_score: Optional[float] = None  # 0-1


class SmartNotificationProfile(NotificationProfile):
    """A notification enriched with AI-driven smart metadata."""
    smart_metadata: Optional[SmartMetadata] = None


class SmartNotificationSettings(BaseModel):
    """User settings for smart notifications."""
    user_id: str
    enabled: bool = True
    surplus_notifications: bool = True
    investment_notifications: bool = True
    overspending_notifications: bool = True
    goal_notifications: bool = True
    savings_notifications: bool = True
    max_daily_nudges: int = Field(default=5, ge=1, le=20)
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    min_surplus_amount: Decimal = Field(default=Decimal("50.00"))
    overspending_threshold_percentage: float = Field(default=80.0, ge=50.0, le=100.0)
    updated_at: datetime


class SmartNotificationCreateRequest(BaseModel):
    """Request to create a smart notification."""
    type: SmartNotificationType
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=500)
    priority: NotificationPriority = NotificationPriority.MEDIUM
    recommended_action: NudgeAction
    action_details: Dict[str, Any] = {}
    amount: Optional[Decimal] = None
    category: Optional[str] = None
    goal_id: Optional[str] = None
    budget_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class SmartNotificationResponse(BaseModel):
    """Response with smart notifications."""
    notifications: List[SmartNotificationProfile]
    total_count: int
    unread_count: int
    high_priority_count: int


# ─────────────────────────────────────────────────────────────────────────────
# Surplus / Overspending / Investment helpers (previously in smart_notifications)
# ─────────────────────────────────────────────────────────────────────────────

class SurplusDetectionResult(BaseModel):
    has_surplus: bool
    surplus_amount: Decimal
    confidence_score: float
    recommended_allocation: Dict[str, Decimal]
    reasoning: str


class OverspendingAnalysis(BaseModel):
    is_overspending: bool
    category: str
    amount_over_budget: Decimal
    percentage_over: float
    trend: str
    suggested_reduction: Decimal
    alternative_actions: List[str]


class InvestmentOpportunityProfile(BaseModel):
    opportunity_id: str
    type: str
    recommended_amount: Decimal
    expected_return: float
    risk_level: str
    reasoning: str
    action_url: Optional[str] = None


class GoalProgressNudge(BaseModel):
    goal_id: str
    goal_name: str
    current_progress: float
    target_amount: Decimal
    current_amount: Decimal
    days_remaining: int
    on_track: bool
    suggested_action: str
    suggested_amount: Optional[Decimal] = None
