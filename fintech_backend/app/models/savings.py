"""
Savings Management Models
Handles data models for savings goals, contributions, and savings account management.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from app.models.base import BaseResponse

class SavingsGoalStatus(str, Enum):
    """Savings goal status"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

class SavingsGoalType(str, Enum):
    """Types of savings goals"""
    GENERAL = "general"
    EMERGENCY_FUND = "emergency_fund"
    VACATION = "vacation"
    HOME_PURCHASE = "home_purchase"
    CAR_PURCHASE = "car_purchase"
    EDUCATION = "education"
    WEDDING = "wedding"
    RETIREMENT = "retirement"
    BUSINESS = "business"
    INVESTMENT = "investment"
    DEBT_PAYOFF = "debt_payoff"
    CUSTOM = "custom"

class ContributionFrequency(str, Enum):
    """Contribution frequency options"""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ONE_TIME = "one_time"

class AutoSaveRule(str, Enum):
    """Auto-save rule types"""
    ROUND_UP = "round_up"          # Round up transactions
    PERCENTAGE = "percentage"       # Save percentage of income
    FIXED_AMOUNT = "fixed_amount"   # Save fixed amount regularly
    SPARE_CHANGE = "spare_change"   # Save spare change
    GOAL_BASED = "goal_based"       # Save based on goal timeline

class SavingsGoalCreateRequest(BaseModel):
    """Request model for creating a savings goal"""
    name: str = Field(..., min_length=1, max_length=100, description="Goal name")
    description: Optional[str] = Field(None, max_length=500, description="Goal description")
    goal_type: SavingsGoalType = Field(..., description="Type of savings goal")
    target_amount: Decimal = Field(..., gt=0, description="Target amount to save")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="Currency code")
    target_date: Optional[date] = Field(None, description="Target completion date")
    auto_contribute: bool = Field(default=False, description="Enable automatic contributions")
    contribution_amount: Optional[Decimal] = Field(None, ge=0, description="Regular contribution amount")
    contribution_frequency: Optional[ContributionFrequency] = Field(None, description="Contribution frequency")
    auto_save_rules: Optional[List[AutoSaveRule]] = Field(default=[], description="Auto-save rules")
    is_private: bool = Field(default=True, description="Whether goal is private")
    
    @validator('target_date')
    def validate_target_date(cls, v):
        if v and v <= date.today():
            raise ValueError('Target date must be in the future')
        return v
    
    @validator('contribution_amount')
    def validate_contribution_amount(cls, v, values):
        if values.get('auto_contribute') and (not v or v <= 0):
            raise ValueError('Contribution amount is required when auto-contribute is enabled')
        return v
    
    @validator('contribution_frequency')
    def validate_contribution_frequency(cls, v, values):
        if values.get('auto_contribute') and not v:
            raise ValueError('Contribution frequency is required when auto-contribute is enabled')
        return v

class SavingsGoalUpdateRequest(BaseModel):
    """Request model for updating a savings goal"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    target_amount: Optional[Decimal] = Field(None, gt=0)
    target_date: Optional[date] = Field(None)
    auto_contribute: Optional[bool] = Field(None)
    contribution_amount: Optional[Decimal] = Field(None, ge=0)
    contribution_frequency: Optional[ContributionFrequency] = Field(None)
    auto_save_rules: Optional[List[AutoSaveRule]] = Field(None)
    is_private: Optional[bool] = Field(None)
    status: Optional[SavingsGoalStatus] = Field(None)
    
    @validator('target_date')
    def validate_target_date(cls, v):
        if v and v <= date.today():
            raise ValueError('Target date must be in the future')
        return v

class ContributionRequest(BaseModel):
    """Request model for making a contribution"""
    amount: Decimal = Field(..., gt=0, description="Contribution amount")
    payment_method_id: Optional[str] = Field(None, description="Payment method ID")
    note: Optional[str] = Field(None, max_length=200, description="Contribution note")
    is_recurring: bool = Field(default=False, description="Whether this is a recurring contribution")

class SavingsGoalProfile(BaseModel):
    """Profile model for savings goals"""
    id: str = Field(..., description="Goal ID")
    name: str = Field(..., description="Goal name")
    description: Optional[str] = Field(None, description="Goal description")
    goal_type: SavingsGoalType = Field(..., description="Goal type")
    target_amount: Decimal = Field(..., description="Target amount")
    current_amount: Decimal = Field(..., description="Current saved amount")
    currency: str = Field(..., description="Currency code")
    progress_percentage: float = Field(..., ge=0, le=100, description="Progress percentage")
    target_date: Optional[date] = Field(None, description="Target completion date")
    days_remaining: Optional[int] = Field(None, description="Days remaining to target date")
    status: SavingsGoalStatus = Field(..., description="Goal status")
    auto_contribute: bool = Field(..., description="Auto-contribute enabled")
    contribution_amount: Optional[Decimal] = Field(None, description="Regular contribution amount")
    contribution_frequency: Optional[ContributionFrequency] = Field(None, description="Contribution frequency")
    auto_save_rules: List[AutoSaveRule] = Field(default=[], description="Auto-save rules")
    total_contributions: int = Field(..., description="Total number of contributions")
    last_contribution_date: Optional[datetime] = Field(None, description="Last contribution date")
    next_contribution_date: Optional[datetime] = Field(None, description="Next scheduled contribution")
    is_private: bool = Field(..., description="Privacy setting")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }

class ContributionProfile(BaseModel):
    """Profile model for contributions"""
    id: str = Field(..., description="Contribution ID")
    goal_id: str = Field(..., description="Savings goal ID")
    amount: Decimal = Field(..., description="Contribution amount")
    currency: str = Field(..., description="Currency code")
    payment_method_id: Optional[str] = Field(None, description="Payment method used")
    payment_method_name: Optional[str] = Field(None, description="Payment method name")
    note: Optional[str] = Field(None, description="Contribution note")
    is_recurring: bool = Field(..., description="Whether this is recurring")
    is_auto_save: bool = Field(..., description="Whether this was auto-saved")
    auto_save_rule: Optional[AutoSaveRule] = Field(None, description="Auto-save rule used")
    transaction_id: Optional[str] = Field(None, description="Related transaction ID")
    contribution_date: datetime = Field(..., description="Contribution timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }

class SavingsGoalHistory(BaseModel):
    """Savings goal history entry"""
    id: str = Field(..., description="History entry ID")
    goal_id: str = Field(..., description="Savings goal ID")
    action: str = Field(..., description="Action performed")
    amount: Optional[Decimal] = Field(None, description="Amount involved")
    previous_amount: Optional[Decimal] = Field(None, description="Previous total amount")
    new_amount: Optional[Decimal] = Field(None, description="New total amount")
    description: str = Field(..., description="Action description")
    timestamp: datetime = Field(..., description="Action timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }

class SavingsGoalStats(BaseModel):
    """Savings goal statistics"""
    total_goals: int = Field(..., description="Total number of goals")
    active_goals: int = Field(..., description="Number of active goals")
    completed_goals: int = Field(..., description="Number of completed goals")
    total_saved: Decimal = Field(..., description="Total amount saved across all goals")
    total_target: Decimal = Field(..., description="Total target amount across all goals")
    average_progress: float = Field(..., ge=0, le=100, description="Average progress percentage")
    total_contributions: int = Field(..., description="Total number of contributions")
    monthly_savings_rate: Decimal = Field(..., description="Average monthly savings rate")
    most_successful_goal_type: Optional[SavingsGoalType] = Field(None, description="Most successful goal type")
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class AutoSaveSettings(BaseModel):
    """Auto-save settings"""
    enabled: bool = Field(..., description="Whether auto-save is enabled")
    round_up_enabled: bool = Field(default=False, description="Round up transactions")
    round_up_multiplier: float = Field(default=1.0, ge=1.0, le=10.0, description="Round up multiplier")
    percentage_save_enabled: bool = Field(default=False, description="Percentage-based saving")
    percentage_save_rate: float = Field(default=0.0, ge=0.0, le=50.0, description="Percentage to save")
    fixed_amount_enabled: bool = Field(default=False, description="Fixed amount saving")
    fixed_amount: Decimal = Field(default=0, ge=0, description="Fixed amount to save")
    fixed_amount_frequency: ContributionFrequency = Field(default=ContributionFrequency.MONTHLY)
    minimum_balance: Decimal = Field(default=0, ge=0, description="Minimum balance to maintain")
    maximum_daily_auto_save: Decimal = Field(default=100, gt=0, description="Maximum daily auto-save amount")

class SavingsInsights(BaseModel):
    """Savings insights and recommendations"""
    current_savings_rate: float = Field(..., description="Current monthly savings rate")
    recommended_savings_rate: float = Field(..., description="Recommended savings rate")
    projected_completion_dates: Dict[str, str] = Field(..., description="Projected completion dates for goals")
    savings_streak: int = Field(..., description="Current savings streak in days")
    best_performing_goal: Optional[str] = Field(None, description="Best performing goal ID")
    underperforming_goals: List[str] = Field(default=[], description="Underperforming goal IDs")
    recommendations: List[str] = Field(default=[], description="Savings recommendations")
    seasonal_trends: Dict[str, float] = Field(default={}, description="Seasonal savings trends")

# Database Models
class SavingsGoalDB(BaseModel):
    """Database model for savings goals"""
    id: str
    user_id: str
    name: str
    description: Optional[str]
    goal_type: SavingsGoalType
    target_amount: Decimal
    current_amount: Decimal
    currency: str
    target_date: Optional[date]
    status: SavingsGoalStatus
    auto_contribute: bool
    contribution_amount: Optional[Decimal]
    contribution_frequency: Optional[ContributionFrequency]
    auto_save_rules: List[AutoSaveRule]
    is_private: bool
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }

class ContributionDB(BaseModel):
    """Database model for contributions"""
    id: str
    user_id: str
    goal_id: str
    amount: Decimal
    currency: str
    payment_method_id: Optional[str]
    note: Optional[str]
    is_recurring: bool
    is_auto_save: bool
    auto_save_rule: Optional[AutoSaveRule]
    transaction_id: Optional[str]
    contribution_date: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }

class SavingsGoalHistoryDB(BaseModel):
    """Database model for savings goal history"""
    id: str
    user_id: str
    goal_id: str
    action: str
    amount: Optional[Decimal]
    previous_amount: Optional[Decimal]
    new_amount: Optional[Decimal]
    description: str
    metadata: Optional[Dict[str, Any]]
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }

class FixedDepositTerm(str, Enum):
    """Fixed deposit term options"""
    MONTHS_6 = "6_months"
    MONTHS_12 = "12_months"
    MONTHS_24 = "24_months"
    MONTHS_36 = "36_months"
    MONTHS_60 = "60_months"

class FixedDepositStatus(str, Enum):
    """Fixed deposit status"""
    ACTIVE = "active"
    MATURED = "matured"
    WITHDRAWN = "withdrawn"
    CANCELLED = "cancelled"

class AutomatedSavingFrequency(str, Enum):
    """Automated saving frequency"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class AutomatedSavingStatus(str, Enum):
    """Automated saving status"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class FixedDepositCreateRequest(BaseModel):
    """Request model for creating a fixed deposit"""
    amount: Decimal = Field(..., gt=0, description="Deposit amount")
    term: FixedDepositTerm = Field(..., description="Deposit term")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="Currency code")
    auto_renew: bool = Field(default=False, description="Auto-renew on maturity")
    roundup_enabled: bool = Field(default=False, description="Enable roundup savings")

class FixedDepositProfile(BaseModel):
    """Profile model for fixed deposits"""
    id: str = Field(..., description="Fixed deposit ID")
    amount: Decimal = Field(..., description="Deposit amount")
    term: FixedDepositTerm = Field(..., description="Deposit term")
    interest_rate: float = Field(..., description="Interest rate")
    maturity_amount: Decimal = Field(..., description="Maturity amount")
    start_date: datetime = Field(..., description="Start date")
    maturity_date: datetime = Field(..., description="Maturity date")
    status: FixedDepositStatus = Field(..., description="Deposit status")
    auto_renew: bool = Field(..., description="Auto-renew enabled")
    roundup_enabled: bool = Field(..., description="Roundup enabled")
    currency: str = Field(..., description="Currency code")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }

class AutomatedSavingCreateRequest(BaseModel):
    """Request model for creating automated saving"""
    name: str = Field(..., min_length=1, max_length=100, description="Saving name")
    amount: Decimal = Field(..., gt=0, description="Amount per transfer")
    frequency: AutomatedSavingFrequency = Field(..., description="Transfer frequency")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="Currency code")
    start_date: Optional[date] = Field(None, description="Start date")

class AutomatedSavingProfile(BaseModel):
    """Profile model for automated savings"""
    id: str = Field(..., description="Automated saving ID")
    name: str = Field(..., description="Saving name")
    amount: Decimal = Field(..., description="Amount per transfer")
    frequency: AutomatedSavingFrequency = Field(..., description="Transfer frequency")
    total_saved: Decimal = Field(..., description="Total amount saved")
    next_deduction: datetime = Field(..., description="Next deduction date")
    status: AutomatedSavingStatus = Field(..., description="Saving status")
    currency: str = Field(..., description="Currency code")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }

