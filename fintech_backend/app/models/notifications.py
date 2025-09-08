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
