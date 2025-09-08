from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from enum import Enum
from decimal import Decimal

class AnalyticsPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"

class TransactionCategory(str, Enum):
    FOOD_DINING = "food_dining"
    TRANSPORTATION = "transportation"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"
    BILLS_UTILITIES = "bills_utilities"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    TRAVEL = "travel"
    GROCERIES = "groceries"
    FUEL = "fuel"
    INSURANCE = "insurance"
    INVESTMENTS = "investments"
    SAVINGS = "savings"
    INCOME = "income"
    TRANSFERS = "transfers"
    OTHER = "other"

class BudgetStatus(str, Enum):
    UNDER_BUDGET = "under_budget"
    ON_TRACK = "on_track"
    OVER_BUDGET = "over_budget"
    EXCEEDED = "exceeded"

class TrendDirection(str, Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"

class AlertType(str, Enum):
    BUDGET_EXCEEDED = "budget_exceeded"
    UNUSUAL_SPENDING = "unusual_spending"
    LOW_BALANCE = "low_balance"
    LARGE_TRANSACTION = "large_transaction"
    GOAL_MILESTONE = "goal_milestone"

# Request Models
class AnalyticsRequest(BaseModel):
    period: AnalyticsPeriod = AnalyticsPeriod.MONTHLY
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    categories: Optional[List[TransactionCategory]] = None
    currency: str = "UGX"
    
    @validator('end_date')
    def validate_dates(cls, v, values):
        if 'start_date' in values and values['start_date'] and v:
            if v <= values['start_date']:
                raise ValueError('End date must be after start date')
        return v

class BudgetRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: TransactionCategory
    amount: Decimal = Field(..., gt=0)
    period: AnalyticsPeriod = AnalyticsPeriod.MONTHLY
    start_date: date
    end_date: Optional[date] = None
    currency: str = "UGX"
    is_active: bool = True
    
    @validator('end_date')
    def validate_dates(cls, v, values):
        if 'start_date' in values and values['start_date'] and v:
            if v <= values['start_date']:
                raise ValueError('End date must be after start date')
        return v

class SpendingAnalysisRequest(BaseModel):
    period: AnalyticsPeriod = AnalyticsPeriod.MONTHLY
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    group_by: str = Field("category", pattern=r'^(category|merchant|day|week|month)$')
    currency: str = "UGX"

class FinancialGoalRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    target_amount: Decimal = Field(..., gt=0)
    target_date: date
    category: TransactionCategory = TransactionCategory.SAVINGS
    currency: str = "UGX"
    description: Optional[str] = Field(None, max_length=500)

# Response Models
class SpendingByCategory(BaseModel):
    category: TransactionCategory
    amount: Decimal
    percentage: float
    transaction_count: int
    average_transaction: Decimal
    trend: TrendDirection
    previous_period_amount: Optional[Decimal] = None
    change_amount: Optional[Decimal] = None
    change_percentage: Optional[float] = None

class MonthlySpending(BaseModel):
    month: str  # YYYY-MM format
    total_amount: Decimal
    categories: List[SpendingByCategory]
    transaction_count: int
    average_daily_spending: Decimal

class SpendingTrend(BaseModel):
    period: str
    amount: Decimal
    transaction_count: int
    date: date

class BudgetProfile(BaseModel):
    id: str
    name: str
    category: TransactionCategory
    budgeted_amount: Decimal
    spent_amount: Decimal
    remaining_amount: Decimal
    percentage_used: float
    status: BudgetStatus
    period: AnalyticsPeriod
    start_date: date
    end_date: Optional[date]
    currency: str
    is_active: bool
    days_remaining: Optional[int] = None
    daily_budget_remaining: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime

class BudgetSummary(BaseModel):
    total_budgets: int
    active_budgets: int
    total_budgeted: Decimal
    total_spent: Decimal
    total_remaining: Decimal
    overall_percentage_used: float
    budgets_over_limit: int
    budgets_on_track: int
    budgets_under_budget: int

class FinancialInsight(BaseModel):
    id: str
    title: str
    description: str
    insight_type: str  # spending_pattern, budget_alert, saving_opportunity, etc.
    category: Optional[TransactionCategory] = None
    amount: Optional[Decimal] = None
    percentage: Optional[float] = None
    action_recommended: str
    priority: str = Field(..., pattern=r'^(low|medium|high|urgent)$')
    created_at: datetime

class CashFlowAnalysis(BaseModel):
    period: str
    total_income: Decimal
    total_expenses: Decimal
    net_cash_flow: Decimal
    income_sources: Dict[str, Decimal]
    expense_categories: Dict[str, Decimal]
    cash_flow_trend: TrendDirection
    previous_period_comparison: Optional[Dict[str, Any]] = None

class FinancialHealthScore(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    spending_score: int = Field(..., ge=0, le=100)
    savings_score: int = Field(..., ge=0, le=100)
    budget_adherence_score: int = Field(..., ge=0, le=100)
    debt_management_score: int = Field(..., ge=0, le=100)
    emergency_fund_score: int = Field(..., ge=0, le=100)
    recommendations: List[str]
    score_breakdown: Dict[str, Any]
    last_calculated: datetime

class ExpenseReport(BaseModel):
    report_id: str
    period: AnalyticsPeriod
    start_date: date
    end_date: date
    currency: str
    total_expenses: Decimal
    total_transactions: int
    average_transaction_amount: Decimal
    largest_expense: Dict[str, Any]
    most_frequent_category: TransactionCategory
    spending_by_category: List[SpendingByCategory]
    daily_averages: List[Dict[str, Any]]
    weekly_trends: List[SpendingTrend]
    generated_at: datetime

class FinancialGoalProfile(BaseModel):
    id: str
    name: str
    target_amount: Decimal
    current_amount: Decimal
    remaining_amount: Decimal
    target_date: date
    days_remaining: int
    progress_percentage: float
    monthly_target: Decimal
    on_track: bool
    category: TransactionCategory
    currency: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class FinancialAlert(BaseModel):
    id: str
    alert_type: AlertType
    title: str
    message: str
    severity: str = Field(..., pattern=r'^(info|warning|critical)$')
    category: Optional[TransactionCategory] = None
    amount: Optional[Decimal] = None
    threshold: Optional[Decimal] = None
    is_read: bool = False
    created_at: datetime
    expires_at: Optional[datetime] = None

# Database Models
class BudgetDB(BaseModel):
    id: str
    user_id: str
    name: str
    category: TransactionCategory
    amount: Decimal
    period: AnalyticsPeriod
    start_date: date
    end_date: Optional[date] = None
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class FinancialGoalDB(BaseModel):
    id: str
    user_id: str
    name: str
    target_amount: Decimal
    current_amount: Decimal = Decimal("0")
    target_date: date
    category: TransactionCategory
    currency: str
    description: Optional[str] = None
    is_completed: bool = False
    created_at: datetime
    updated_at: datetime

class FinancialAlertDB(BaseModel):
    id: str
    user_id: str
    alert_type: AlertType
    title: str
    message: str
    severity: str
    category: Optional[TransactionCategory] = None
    amount: Optional[Decimal] = None
    threshold: Optional[Decimal] = None
    is_read: bool = False
    created_at: datetime
    expires_at: Optional[datetime] = None

class TransactionAnalyticsDB(BaseModel):
    id: str
    user_id: str
    transaction_id: str
    amount: Decimal
    category: TransactionCategory
    merchant: Optional[str] = None
    description: Optional[str] = None
    transaction_date: date
    currency: str
    is_income: bool = False
    created_at: datetime
