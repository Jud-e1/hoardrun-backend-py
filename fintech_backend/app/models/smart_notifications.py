"""
Smart Notification Models
Decision nudges and intelligent financial notifications
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from decimal import Decimal

class SmartNotificationType(str, Enum):
    """Types of smart notifications (decision nudges)"""
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

class NudgePriority(str, Enum):
    """Priority levels for nudges"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class NudgeAction(str, Enum):
    """Recommended actions for nudges"""
    SAVE_NOW = "save_now"
    INVEST_NOW = "invest_now"
    REDUCE_SPENDING = "reduce_spending"
    REVIEW_BUDGET = "review_budget"
    SET_GOAL = "set_goal"
    INCREASE_CONTRIBUTION = "increase_contribution"
    PAUSE_SPENDING = "pause_spending"
    REVIEW_SUBSCRIPTIONS = "review_subscriptions"

class SmartNotificationProfile(BaseModel):
    """Smart notification with actionable insights"""
    id: str
    user_id: str
    type: SmartNotificationType
    title: str
    message: str
    priority: NudgePriority
    recommended_action: NudgeAction
    action_details: Dict[str, Any]  # Specific action parameters
    
    # Financial context
    amount: Optional[Decimal] = None
    category: Optional[str] = None
    goal_id: Optional[str] = None
    budget_id: Optional[str] = None
    
    # Engagement tracking
    is_read: bool = False
    is_acted_upon: bool = False
    action_taken_at: Optional[datetime] = None
    
    # Metadata
    created_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class SurplusDetectionResult(BaseModel):
    """Result of surplus detection analysis"""
    has_surplus: bool
    surplus_amount: Decimal
    confidence_score: float  # 0-1
    recommended_allocation: Dict[str, Decimal]  # savings, investment, debt
    reasoning: str

class OverspendingAnalysis(BaseModel):
    """Analysis of overspending patterns"""
    is_overspending: bool
    category: str
    amount_over_budget: Decimal
    percentage_over: float
    trend: str  # increasing, stable, decreasing
    suggested_reduction: Decimal
    alternative_actions: List[str]

class InvestmentOpportunityProfile(BaseModel):
    """Investment opportunity recommendation"""
    opportunity_id: str
    type: str  # stocks, bonds, savings, etc.
    recommended_amount: Decimal
    expected_return: float
    risk_level: str  # low, medium, high
    reasoning: str
    action_url: Optional[str] = None

class GoalProgressNudge(BaseModel):
    """Nudge for goal progress"""
    goal_id: str
    goal_name: str
    current_progress: float  # percentage
    target_amount: Decimal
    current_amount: Decimal
    days_remaining: int
    on_track: bool
    suggested_action: str
    suggested_amount: Optional[Decimal] = None

class BehavioralTrigger(BaseModel):
    """Behavioral trigger for smart notifications"""
    trigger_type: str
    condition_met: bool
    threshold: Any
    current_value: Any
    last_triggered: Optional[datetime] = None
    frequency_limit: str  # daily, weekly, monthly

class SmartNotificationSettings(BaseModel):
    """User settings for smart notifications"""
    user_id: str
    enabled: bool = True
    
    # Notification type preferences
    surplus_notifications: bool = True
    investment_notifications: bool = True
    overspending_notifications: bool = True
    goal_notifications: bool = True
    savings_notifications: bool = True
    
    # Frequency settings
    max_daily_nudges: int = Field(default=5, ge=1, le=20)
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    
    # Thresholds
    min_surplus_amount: Decimal = Field(default=Decimal("50.00"))
    overspending_threshold_percentage: float = Field(default=80.0, ge=50.0, le=100.0)
    
    updated_at: datetime

class SmartNotificationCreateRequest(BaseModel):
    """Request to create a smart notification"""
    type: SmartNotificationType
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=500)
    priority: NudgePriority = NudgePriority.MEDIUM
    recommended_action: NudgeAction
    action_details: Dict[str, Any]
    amount: Optional[Decimal] = None
    category: Optional[str] = None
    goal_id: Optional[str] = None
    budget_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class SmartNotificationResponse(BaseModel):
    """Response with smart notifications"""
    notifications: List[SmartNotificationProfile]
    total_count: int
    unread_count: int
    high_priority_count: int

