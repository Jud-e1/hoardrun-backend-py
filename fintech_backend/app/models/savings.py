"""
Savings management models for the fintech backend.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from app.models.base import BaseResponse, TimestampMixin


class SavingsGoalType(str, Enum):
    """Types of savings goals."""
    EMERGENCY_FUND = "emergency_fund"
    VACATION = "vacation"
    HOME_PURCHASE = "home_purchase"
    CAR_PURCHASE = "car_purchase"
    EDUCATION = "education"
    WEDDING = "wedding"
    RETIREMENT = "retirement"
    INVESTMENT = "investment"
    DEBT_PAYOFF = "debt_payoff"
    GENERAL = "general"
    CUSTOM = "custom"


class SavingsGoalStatus(str, Enum):
    """Status of savings goals."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"


class AutoSaveFrequency(str, Enum):
    """Frequency for automatic savings."""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class AutoSaveType(str, Enum):
    """Types of automatic savings."""
    FIXED_AMOUNT = "fixed_amount"
    PERCENTAGE = "percentage"
    ROUND_UP = "round_up"
    SPARE_CHANGE = "spare_change"
    INCOME_BASED = "income_based"


class SavingsAccountType(str, Enum):
    """Types of savings accounts."""
    BASIC_SAVINGS = "basic_savings"
    HIGH_YIELD = "high_yield"
    MONEY_MARKET = "money_market"
    CD = "cd"
    GOAL_BASED = "goal_based"
    EMERGENCY_FUND = "emergency_fund"


class ContributionMethod(str, Enum):
    """Methods for making contributions."""
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    ROUND_UP = "round_up"
    SPARE_CHANGE = "spare_change"
    BANK_TRANSFER = "bank_transfer"


class SavingsGoal(BaseModel, TimestampMixin):
    """Savings goal model."""
    goal_id: str = Field(..., description="Unique goal identifier")
    user_id: str = Field(..., description="User identifier")
    savings_account_id: str = Field(..., description="Associated savings account")
    
    # Goal details
    name: str = Field(..., description="Goal name")
    description: Optional[str] = Field(None, description="Goal description")
    goal_type: SavingsGoalType = Field(..., description="Type of savings goal")
    status: SavingsGoalStatus = Field(..., description="Goal status")
    
    # Financial targets
    target_amount: Decimal = Field(..., gt=0, description="Target savings amount")
    current_amount: Decimal = Field(default=Decimal("0"), description="Current saved amount")
    initial_deposit: Decimal = Field(default=Decimal("0"), description="Initial deposit amount")
    
    # Timeline
    target_date: Optional[date] = Field(None, description="Target completion date")
    start_date: date = Field(default_factory=date.today, description="Goal start date")
    completed_date: Optional[date] = Field(None, description="Actual completion date")
    
    # Progress tracking
    progress_percentage: Decimal = Field(default=Decimal("0"), description="Progress percentage")
    monthly_target: Optional[Decimal] = Field(None, description="Suggested monthly contribution")
    days_remaining: Optional[int] = Field(None, description="Days until target date")
    
    # Auto-save settings
    auto_save_enabled: bool = Field(default=False, description="Enable automatic saving")
    auto_save_amount: Optional[Decimal] = Field(None, description="Auto-save amount")
    auto_save_frequency: Optional[AutoSaveFrequency] = Field(None, description="Auto-save frequency")
    auto_save_type: Optional[AutoSaveType] = Field(None, description="Type of auto-save")
    source_account_id: Optional[str] = Field(None, description="Source account for auto-save")
    
    # Milestone tracking
    milestones: List[Dict[str, Any]] = Field(default_factory=list, description="Goal milestones")
    last_contribution_date: Optional[date] = Field(None, description="Last contribution date")
    largest_contribution: Decimal = Field(default=Decimal("0"), description="Largest single contribution")
    total_contributions: int = Field(default=0, description="Total number of contributions")
    
    # Motivation and gamification
    emoji: Optional[str] = Field(None, description="Goal emoji/icon")
    color: Optional[str] = Field(None, description="Goal color theme")
    celebration_enabled: bool = Field(default=True, description="Enable milestone celebrations")
    
    @property
    def is_on_track(self) -> bool:
        """Check if goal is on track based on timeline."""
        if not self.target_date:
            return True
        
        days_total = (self.target_date - self.start_date).days
        days_elapsed = (date.today() - self.start_date).days
        
        if days_total <= 0:
            return self.current_amount >= self.target_amount
        
        expected_progress = (days_elapsed / days_total) * 100
        return float(self.progress_percentage) >= expected_progress * 0.9  # 10% tolerance
    
    @validator('progress_percentage', always=True)
    def calculate_progress(cls, v, values):
        if 'current_amount' in values and 'target_amount' in values and values['target_amount'] > 0:
            return (values['current_amount'] / values['target_amount']) * 100
        return Decimal("0")


class SavingsAccount(BaseModel, TimestampMixin):
    """Savings account model."""
    savings_account_id: str = Field(..., description="Unique savings account identifier")
    user_id: str = Field(..., description="Account owner user ID")
    linked_account_id: str = Field(..., description="Linked checking/primary account")
    
    # Account details
    account_name: str = Field(..., description="Account name")
    account_type: SavingsAccountType = Field(..., description="Type of savings account")
    account_number: str = Field(..., description="Account number")
    
    # Balances and rates
    balance: Decimal = Field(default=Decimal("0"), description="Current balance")
    available_balance: Decimal = Field(default=Decimal("0"), description="Available balance")
    interest_rate: Decimal = Field(..., description="Annual interest rate")
    apy: Decimal = Field(..., description="Annual percentage yield")
    
    # Interest tracking
    interest_earned_ytd: Decimal = Field(default=Decimal("0"), description="Interest earned year-to-date")
    interest_earned_total: Decimal = Field(default=Decimal("0"), description="Total interest earned")
    last_interest_payment: Optional[date] = Field(None, description="Last interest payment date")
    
    # Account settings
    minimum_balance: Decimal = Field(default=Decimal("0"), description="Minimum balance requirement")
    maximum_balance: Optional[Decimal] = Field(None, description="Maximum balance limit")
    withdrawal_limit_monthly: Optional[int] = Field(None, description="Monthly withdrawal limit")
    withdrawal_count_current: int = Field(default=0, description="Current month withdrawal count")
    
    # Terms and conditions
    term_length_months: Optional[int] = Field(None, description="Term length for CDs")
    maturity_date: Optional[date] = Field(None, description="Maturity date for term accounts")
    early_withdrawal_penalty: Optional[Decimal] = Field(None, description="Early withdrawal penalty")
    
    # Account status
    is_active: bool = Field(default=True, description="Account active status")
    is_locked: bool = Field(default=False, description="Account locked status")
    auto_transfer_enabled: bool = Field(default=False, description="Auto transfer enabled")
    
    @property
    def projected_annual_interest(self) -> Decimal:
        """Calculate projected annual interest based on current balance."""
        return self.balance * (self.apy / 100)


class SavingsContribution(BaseModel, TimestampMixin):
    """Savings contribution record."""
    contribution_id: str = Field(..., description="Unique contribution identifier")
    goal_id: Optional[str] = Field(None, description="Associated goal ID")
    savings_account_id: str = Field(..., description="Savings account ID")
    source_account_id: str = Field(..., description="Source account ID")
    
    # Contribution details
    amount: Decimal = Field(..., gt=0, description="Contribution amount")
    contribution_method: ContributionMethod = Field(..., description="Method of contribution")
    transaction_id: str = Field(..., description="Associated transaction ID")
    
    # Metadata
    description: Optional[str] = Field(None, description="Contribution description")
    is_automatic: bool = Field(default=False, description="Whether contribution was automatic")
    round_up_amount: Optional[Decimal] = Field(None, description="Round-up amount if applicable")
    original_transaction_amount: Optional[Decimal] = Field(None, description="Original transaction for round-ups")
    
    # Status
    status: str = Field(default="completed", description="Contribution status")
    processed_at: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")


class AutoSaveRule(BaseModel, TimestampMixin):
    """Automatic savings rule."""
    rule_id: str = Field(..., description="Unique rule identifier")
    user_id: str = Field(..., description="User identifier")
    goal_id: Optional[str] = Field(None, description="Associated goal ID")
    savings_account_id: str = Field(..., description="Destination savings account")
    source_account_id: str = Field(..., description="Source account for transfers")
    
    # Rule configuration
    name: str = Field(..., description="Rule name")
    auto_save_type: AutoSaveType = Field(..., description="Type of auto-save")
    frequency: AutoSaveFrequency = Field(..., description="Savings frequency")
    
    # Amount settings
    fixed_amount: Optional[Decimal] = Field(None, description="Fixed amount for fixed_amount type")
    percentage: Optional[Decimal] = Field(None, description="Percentage for percentage type")
    minimum_amount: Decimal = Field(default=Decimal("1.00"), description="Minimum transfer amount")
    maximum_amount: Optional[Decimal] = Field(None, description="Maximum transfer amount")
    
    # Scheduling
    next_execution: datetime = Field(..., description="Next scheduled execution")
    last_execution: Optional[datetime] = Field(None, description="Last execution timestamp")
    
    # Conditions
    balance_threshold: Optional[Decimal] = Field(None, description="Minimum source balance threshold")
    income_multiplier: Optional[Decimal] = Field(None, description="Income-based multiplier")
    
    # Status and tracking
    is_active: bool = Field(default=True, description="Rule active status")
    total_saved: Decimal = Field(default=Decimal("0"), description="Total amount saved by this rule")
    execution_count: int = Field(default=0, description="Number of executions")
    
    # Settings
    pause_on_low_balance: bool = Field(default=True, description="Pause if source balance too low")
    notify_on_execution: bool = Field(default=True, description="Send notification on execution")


class SavingsChallenge(BaseModel, TimestampMixin):
    """Savings challenge model."""
    challenge_id: str = Field(..., description="Unique challenge identifier")
    user_id: str = Field(..., description="User identifier")
    goal_id: Optional[str] = Field(None, description="Associated goal ID")
    
    # Challenge details
    name: str = Field(..., description="Challenge name")
    description: str = Field(..., description="Challenge description")
    challenge_type: str = Field(..., description="Type of challenge")
    
    # Challenge parameters
    target_amount: Decimal = Field(..., gt=0, description="Challenge target amount")
    duration_days: int = Field(..., gt=0, description="Challenge duration in days")
    daily_target: Decimal = Field(..., description="Daily savings target")
    
    # Progress tracking
    current_amount: Decimal = Field(default=Decimal("0"), description="Current saved amount")
    days_completed: int = Field(default=0, description="Days completed")
    streak: int = Field(default=0, description="Current streak")
    longest_streak: int = Field(default=0, description="Longest streak achieved")
    
    # Timeline
    start_date: date = Field(..., description="Challenge start date")
    end_date: date = Field(..., description="Challenge end date")
    completed_date: Optional[date] = Field(None, description="Completion date")
    
    # Status
    status: str = Field(default="active", description="Challenge status")
    is_completed: bool = Field(default=False, description="Whether challenge is completed")
    
    # Rewards and motivation
    reward_description: Optional[str] = Field(None, description="Reward description")
    milestone_rewards: List[Dict[str, Any]] = Field(default_factory=list, description="Milestone rewards")
    
    @property
    def progress_percentage(self) -> Decimal:
        """Calculate challenge progress percentage."""
        if self.target_amount > 0:
            return min((self.current_amount / self.target_amount) * 100, Decimal("100"))
        return Decimal("0")
    
    @property
    def days_remaining(self) -> int:
        """Calculate days remaining in challenge."""
        return max(0, (self.end_date - date.today()).days)


class SavingsInsight(BaseModel):
    """Savings insight and recommendation."""
    insight_id: str = Field(..., description="Unique insight identifier")
    user_id: str = Field(..., description="User identifier")
    insight_type: str = Field(..., description="Type of insight")
    title: str = Field(..., description="Insight title")
    description: str = Field(..., description="Insight description")
    
    # Recommendation data
    recommended_action: Optional[str] = Field(None, description="Recommended action")
    potential_savings: Optional[Decimal] = Field(None, description="Potential savings amount")
    confidence_score: float = Field(..., description="Confidence score (0-1)")
    
    # Metadata
    category: str = Field(..., description="Insight category")
    priority: str = Field(default="medium", description="Priority level")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(None, description="Insight expiration")
    
    # User interaction
    is_read: bool = Field(default=False, description="Whether user has read insight")
    is_dismissed: bool = Field(default=False, description="Whether user dismissed insight")
    action_taken: Optional[str] = Field(None, description="Action taken by user")


# Request models
class SavingsGoalCreateRequest(BaseModel):
    """Request model for creating savings goals."""
    name: str = Field(..., min_length=1, max_length=100, description="Goal name")
    description: Optional[str] = Field(None, max_length=500, description="Goal description")
    goal_type: SavingsGoalType = Field(..., description="Type of savings goal")
    target_amount: Decimal = Field(..., gt=0, description="Target savings amount")
    target_date: Optional[date] = Field(None, description="Target completion date")
    savings_account_id: str = Field(..., description="Associated savings account")
    initial_deposit: Optional[Decimal] = Field(None, gt=0, description="Initial deposit amount")
    auto_save_enabled: bool = Field(default=False, description="Enable automatic saving")
    auto_save_amount: Optional[Decimal] = Field(None, gt=0, description="Auto-save amount")
    auto_save_frequency: Optional[AutoSaveFrequency] = Field(None, description="Auto-save frequency")
    source_account_id: Optional[str] = Field(None, description="Source account for auto-save")
    emoji: Optional[str] = Field(None, description="Goal emoji")
    color: Optional[str] = Field(None, description="Goal color")


class SavingsGoalUpdateRequest(BaseModel):
    """Request model for updating savings goals."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Goal name")
    description: Optional[str] = Field(None, max_length=500, description="Goal description")
    target_amount: Optional[Decimal] = Field(None, gt=0, description="Target savings amount")
    target_date: Optional[date] = Field(None, description="Target completion date")
    auto_save_enabled: Optional[bool] = Field(None, description="Enable automatic saving")
    auto_save_amount: Optional[Decimal] = Field(None, gt=0, description="Auto-save amount")
    auto_save_frequency: Optional[AutoSaveFrequency] = Field(None, description="Auto-save frequency")
    emoji: Optional[str] = Field(None, description="Goal emoji")
    color: Optional[str] = Field(None, description="Goal color")


class SavingsAccountCreateRequest(BaseModel):
    """Request model for creating savings accounts."""
    account_name: str = Field(..., min_length=1, max_length=100, description="Account name")
    account_type: SavingsAccountType = Field(..., description="Type of savings account")
    linked_account_id: str = Field(..., description="Linked checking/primary account")
    initial_deposit: Optional[Decimal] = Field(None, gt=0, description="Initial deposit amount")
    auto_transfer_enabled: bool = Field(default=False, description="Enable auto transfers")
    interest_rate: Optional[Decimal] = Field(None, description="Custom interest rate")


class ContributionRequest(BaseModel):
    """Request model for making savings contributions."""
    goal_id: Optional[str] = Field(None, description="Goal ID (optional)")
    savings_account_id: str = Field(..., description="Savings account ID")
    amount: Decimal = Field(..., gt=0, description="Contribution amount")
    source_account_id: str = Field(..., description="Source account ID")
    description: Optional[str] = Field(None, max_length=200, description="Contribution description")
    contribution_method: ContributionMethod = Field(default=ContributionMethod.MANUAL, description="Contribution method")


class AutoSaveRuleCreateRequest(BaseModel):
    """Request model for creating auto-save rules."""
    name: str = Field(..., min_length=1, max_length=100, description="Rule name")
    goal_id: Optional[str] = Field(None, description="Associated goal ID")
    savings_account_id: str = Field(..., description="Destination savings account")
    source_account_id: str = Field(..., description="Source account")
    auto_save_type: AutoSaveType = Field(..., description="Type of auto-save")
    frequency: AutoSaveFrequency = Field(..., description="Savings frequency")
    fixed_amount: Optional[Decimal] = Field(None, gt=0, description="Fixed amount")
    percentage: Optional[Decimal] = Field(None, gt=0, le=100, description="Percentage")
    minimum_amount: Decimal = Field(default=Decimal("1.00"), description="Minimum transfer amount")
    maximum_amount: Optional[Decimal] = Field(None, description="Maximum transfer amount")
    balance_threshold: Optional[Decimal] = Field(None, description="Minimum source balance threshold")


class SavingsChallengeCreateRequest(BaseModel):
    """Request model for creating savings challenges."""
    name: str = Field(..., min_length=1, max_length=100, description="Challenge name")
    challenge_type: str = Field(..., description="Type of challenge")
    target_amount: Decimal = Field(..., gt=0, description="Challenge target amount")
    duration_days: int = Field(..., gt=0, le=365, description="Challenge duration in days")
    goal_id: Optional[str] = Field(None, description="Associated goal ID")
    start_date: date = Field(default_factory=date.today, description="Challenge start date")


class WithdrawalRequest(BaseModel):
    """Request model for savings withdrawals."""
    savings_account_id: str = Field(..., description="Savings account ID")
    amount: Decimal = Field(..., gt=0, description="Withdrawal amount")
    destination_account_id: str = Field(..., description="Destination account ID")
    reason: Optional[str] = Field(None, max_length=200, description="Withdrawal reason")
    goal_id: Optional[str] = Field(None, description="Goal ID if withdrawing from goal")


# Response models
class SavingsGoalResponse(BaseResponse):
    """Response model for savings goal operations."""
    goal: SavingsGoal = Field(..., description="Savings goal details")


class SavingsGoalListResponse(BaseResponse):
    """Response model for savings goal listings."""
    goals: List[SavingsGoal] = Field(..., description="List of savings goals")
    total_count: int = Field(..., description="Total number of goals")
    active_goals: int = Field(..., description="Number of active goals")
    completed_goals: int = Field(..., description="Number of completed goals")
    total_target_amount: Decimal = Field(..., description="Total target amount across all goals")
    total_saved: Decimal = Field(..., description="Total amount saved across all goals")


class SavingsAccountResponse(BaseResponse):
    """Response model for savings account operations."""
    account: SavingsAccount = Field(..., description="Savings account details")


class SavingsAccountListResponse(BaseResponse):
    """Response model for savings account listings."""
    accounts: List[SavingsAccount] = Field(..., description="List of savings accounts")
    total_count: int = Field(..., description="Total number of accounts")
    total_balance: Decimal = Field(..., description="Total balance across all accounts")
    total_interest_ytd: Decimal = Field(..., description="Total interest earned YTD")


class ContributionResponse(BaseResponse):
    """Response model for contribution operations."""
    contribution: SavingsContribution = Field(..., description="Contribution details")


class ContributionListResponse(BaseResponse):
    """Response model for contribution listings."""
    contributions: List[SavingsContribution] = Field(..., description="List of contributions")
    total_count: int = Field(..., description="Total number of contributions")
    total_amount: Decimal = Field(..., description="Total contribution amount")
    average_contribution: Decimal = Field(..., description="Average contribution amount")


class AutoSaveRuleResponse(BaseResponse):
    """Response model for auto-save rule operations."""
    rule: AutoSaveRule = Field(..., description="Auto-save rule details")


class AutoSaveRuleListResponse(BaseResponse):
    """Response model for auto-save rule listings."""
    rules: List[AutoSaveRule] = Field(..., description="List of auto-save rules")
    total_count: int = Field(..., description="Total number of rules")
    active_rules: int = Field(..., description="Number of active rules")
    total_monthly_savings: Decimal = Field(..., description="Total estimated monthly savings")


class SavingsChallengeResponse(BaseResponse):
    """Response model for savings challenge operations."""
    challenge: SavingsChallenge = Field(..., description="Savings challenge details")


class SavingsChallengeListResponse(BaseResponse):
    """Response model for savings challenge listings."""
    challenges: List[SavingsChallenge] = Field(..., description="List of savings challenges")
    total_count: int = Field(..., description="Total number of challenges")
    active_challenges: int = Field(..., description="Number of active challenges")
    completed_challenges: int = Field(..., description="Number of completed challenges")


class SavingsInsightResponse(BaseResponse):
    """Response model for savings insights."""
    insights: List[SavingsInsight] = Field(..., description="List of savings insights")
    total_count: int = Field(..., description="Total number of insights")
    unread_count: int = Field(..., description="Number of unread insights")
    high_priority_count: int = Field(..., description="Number of high priority insights")


class SavingsSummaryResponse(BaseResponse):
    """Response model for savings summary."""
    total_savings: Decimal = Field(..., description="Total savings across all accounts")
    total_goals: int = Field(..., description="Total number of goals")
    active_goals: int = Field(..., description="Number of active goals")
    goals_on_track: int = Field(..., description="Number of goals on track")
    monthly_auto_savings: Decimal = Field(..., description="Monthly automatic savings amount")
    interest_earned_ytd: Decimal = Field(..., description="Interest earned year-to-date")
    average_savings_rate: Decimal = Field(..., description="Average monthly savings rate")
    emergency_fund_ratio: Decimal = Field(..., description="Emergency fund coverage ratio")
    top_performing_goals: List[Dict[str, Any]] = Field(..., description="Top performing goals")
    upcoming_milestones: List[Dict[str, Any]] = Field(..., description="Upcoming goal milestones")


class SavingsAnalyticsResponse(BaseResponse):
    """Response model for savings analytics."""
    period_start: date = Field(..., description="Analysis period start")
    period_end: date = Field(..., description="Analysis period end")
    total_contributions: Decimal = Field(..., description="Total contributions in period")
    total_withdrawals: Decimal = Field(..., description="Total withdrawals in period")
    net_savings: Decimal = Field(..., description="Net savings in period")
    contribution_frequency: Dict[str, int] = Field(..., description="Contribution frequency by method")
    monthly_trends: Dict[str, Decimal] = Field(..., description="Monthly savings trends")
    goal_completion_rate: Decimal = Field(..., description="Goal completion rate")
    average_time_to_goal: Optional[int] = Field(None, description="Average days to complete goals")
    savings_velocity: Decimal = Field(..., description="Savings velocity (amount per day)")


class RoundUpSummaryResponse(BaseResponse):
    """Response model for round-up savings summary."""
    total_round_ups: Decimal = Field(..., description="Total round-up savings")
    transaction_count: int = Field(..., description="Number of transactions with round-ups")
    average_round_up: Decimal = Field(..., description="Average round-up amount")
    monthly_projection: Decimal = Field(..., description="Projected monthly round-up savings")
    top_categories: Dict[str, Decimal] = Field(..., description="Top categories generating round-ups")
    recent_round_ups: List[Dict[str, Any]] = Field(..., description="Recent round-up transactions")
