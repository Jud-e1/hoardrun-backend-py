"""
Pydantic models for dashboard and analytics data structures.
"""
from decimal import Decimal
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from pydantic import Field, field_validator
from .base import BaseModel, BaseRequest, BaseResponse


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationType(str, Enum):
    """Types of notifications."""
    TRANSACTION_ALERT = "transaction_alert"
    SPENDING_LIMIT = "spending_limit"
    ACCOUNT_ALERT = "account_alert"
    SECURITY_ALERT = "security_alert"
    INVESTMENT_ALERT = "investment_alert"
    PAYMENT_DUE = "payment_due"
    SYSTEM_MAINTENANCE = "system_maintenance"


class CurrencyAmount(BaseModel):
    """Model for currency amounts with formatting."""
    amount: Decimal = Field(..., description="Numeric amount")
    currency: str = Field(..., description="Currency code")
    formatted: str = Field(..., description="Formatted amount string")
    symbol: str = Field(..., description="Currency symbol")


class BalanceSummary(BaseModel):
    """Model for balance summary information."""
    total_balance: CurrencyAmount = Field(..., description="Total balance across all accounts")
    available_balance: CurrencyAmount = Field(..., description="Available balance for spending")
    net_worth: CurrencyAmount = Field(..., description="Total net worth")


class AssetSummary(BaseModel):
    """Model for asset breakdown."""
    total_assets: CurrencyAmount = Field(..., description="Total assets value")
    cash_and_equivalents: CurrencyAmount = Field(..., description="Cash and cash equivalents")
    investments: CurrencyAmount = Field(..., description="Investment portfolio value")


class LiabilitySummary(BaseModel):
    """Model for liability information."""
    total_liabilities: CurrencyAmount = Field(..., description="Total liabilities")


class FinancialSummary(BaseModel):
    """Model for complete financial summary."""
    balances: BalanceSummary = Field(..., description="Balance information")
    assets: AssetSummary = Field(..., description="Asset breakdown")
    liabilities: LiabilitySummary = Field(..., description="Liability information")


class SpendingCategory(BaseModel):
    """Model for spending category breakdown."""
    category: str = Field(..., description="Spending category name")
    amount: CurrencyAmount = Field(..., description="Amount spent in category")
    percentage: Dict[str, Any] = Field(..., description="Percentage of total spending")
    transaction_count: int = Field(..., description="Number of transactions in category")


class MonthlyTrend(BaseModel):
    """Model for monthly spending trend."""
    month: str = Field(..., description="Month in YYYY-MM format")
    spending: CurrencyAmount = Field(..., description="Total spending for the month")
    transaction_count: int = Field(..., description="Number of transactions")
    avg_transaction: CurrencyAmount = Field(..., description="Average transaction amount")


class SpendingAnalytics(BaseModel):
    """Model for spending analytics data."""
    summary: Dict[str, Any] = Field(..., description="Spending summary")
    category_breakdown: List[SpendingCategory] = Field(..., description="Spending by category")
    monthly_trends: List[MonthlyTrend] = Field(..., description="Monthly spending trends")


class RecentTransaction(BaseModel):
    """Model for recent transaction display."""
    transaction_id: str = Field(..., description="Transaction ID")
    amount: CurrencyAmount = Field(..., description="Transaction amount")
    type: str = Field(..., description="Transaction type")
    merchant: Optional[str] = Field(None, description="Merchant name")
    category: Optional[str] = Field(None, description="Transaction category")
    date: datetime = Field(..., description="Transaction date")
    status: str = Field(..., description="Transaction status")


class Notification(BaseModel):
    """Model for user notifications."""
    notification_id: str = Field(..., description="Notification ID")
    type: NotificationType = Field(..., description="Notification type")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL, description="Notification priority")
    is_read: bool = Field(default=False, description="Whether notification has been read")
    created_at: datetime = Field(..., description="Notification creation time")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional notification data")
    action_required: bool = Field(default=False, description="Whether user action is required")


# Request Models
class DashboardSummaryRequest(BaseRequest):
    """Request model for dashboard summary."""
    user_id: str = Field(..., description="User ID")
    include_pending: bool = Field(default=True, description="Include pending transactions")
    date_range_days: int = Field(default=30, ge=1, le=365, description="Date range for recent data")


class AnalyticsRequest(BaseRequest):
    """Request model for analytics data."""
    user_id: str = Field(..., description="User ID")
    period_days: int = Field(default=30, ge=1, le=365, description="Analysis period in days")
    category_filter: Optional[List[str]] = Field(None, description="Filter by specific categories")
    include_trends: bool = Field(default=True, description="Include trend analysis")


class NotificationsRequest(BaseRequest):
    """Request model for notifications."""
    user_id: str = Field(..., description="User ID")
    unread_only: bool = Field(default=False, description="Return only unread notifications")
    notification_type: Optional[NotificationType] = Field(None, description="Filter by notification type")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of notifications")


# Response Models
class DashboardSummaryResponse(BaseResponse):
    """Response model for dashboard summary."""
    data: Dict[str, Any] = Field(..., description="Dashboard summary data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "data": {
                    "financial_summary": {
                        "balances": {
                            "total_balance": {
                                "amount": 25000.50,
                                "currency": "USD",
                                "formatted": "$25,000.50",
                                "symbol": "$"
                            }
                        }
                    },
                    "recent_activity": [],
                    "notifications_count": 3
                },
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }


class AnalyticsResponse(BaseResponse):
    """Response model for analytics data."""
    data: SpendingAnalytics = Field(..., description="Spending analytics data")


class NotificationsResponse(BaseResponse):
    """Response model for notifications."""
    data: List[Notification] = Field(..., description="List of notifications")
    unread_count: int = Field(..., description="Number of unread notifications")


class NotificationMarkReadRequest(BaseRequest):
    """Request model for marking notifications as read."""
    notification_ids: List[str] = Field(..., description="List of notification IDs to mark as read")
    
    @field_validator('notification_ids')
    @classmethod
    def validate_notification_ids(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one notification ID must be provided")
        if len(v) > 50:
            raise ValueError("Cannot mark more than 50 notifications at once")
        return v


class NotificationMarkReadResponse(BaseResponse):
    """Response model for notification mark as read operation."""
    data: Dict[str, Any] = Field(..., description="Operation result")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "data": {
                    "marked_read": 3,
                    "not_found": 0,
                    "already_read": 1
                },
                "message": "Notifications marked as read successfully",
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }
