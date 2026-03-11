"""
AI Financial Guidance Models
Personalized financial recommendations and investment readiness scoring
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from decimal import Decimal

# Enums
class RecommendationType(str, Enum):
    """Types of financial recommendations"""
    SAVE_MORE = "save_more"
    REDUCE_SPENDING = "reduce_spending"
    INVEST_NOW = "invest_now"
    BUILD_EMERGENCY_FUND = "build_emergency_fund"
    PAY_OFF_DEBT = "pay_off_debt"
    INCREASE_INCOME = "increase_income"
    OPTIMIZE_BUDGET = "optimize_budget"
    DIVERSIFY_INVESTMENTS = "diversify_investments"
    REVIEW_SUBSCRIPTIONS = "review_subscriptions"
    SET_FINANCIAL_GOALS = "set_financial_goals"

class RecommendationPriority(str, Enum):
    """Priority levels for recommendations"""
    CRITICAL = "critical"  # Immediate action needed
    HIGH = "high"  # Important, act soon
    MEDIUM = "medium"  # Beneficial, act when ready
    LOW = "low"  # Optional improvement

class InvestmentReadinessLevel(str, Enum):
    """Investment readiness levels"""
    NOT_READY = "not_ready"  # Score 0-40
    GETTING_READY = "getting_ready"  # Score 41-60
    READY = "ready"  # Score 61-80
    HIGHLY_READY = "highly_ready"  # Score 81-100

class RiskTolerance(str, Enum):
    """Risk tolerance levels"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"

class FinancialPersona(str, Enum):
    """User financial personas based on behavior"""
    SAVER = "saver"  # High savings, low spending
    SPENDER = "spender"  # High spending, low savings
    INVESTOR = "investor"  # Active investment behavior
    BALANCED = "balanced"  # Balanced approach
    BEGINNER = "beginner"  # New to financial management

# Request Models
class AIGuidanceRequest(BaseModel):
    """Request for AI financial guidance"""
    include_recommendations: bool = True
    include_investment_readiness: bool = True
    include_insights: bool = True
    time_horizon_days: int = Field(default=90, ge=30, le=365)

# Response Models
class PersonalizedRecommendation(BaseModel):
    """A personalized financial recommendation"""
    id: str
    type: RecommendationType
    title: str
    description: str
    priority: RecommendationPriority
    impact_score: int = Field(..., ge=0, le=100, description="Expected impact on financial health")
    effort_level: str = Field(..., pattern=r'^(low|medium|high)$')
    estimated_savings: Optional[Decimal] = Field(None, description="Estimated monthly savings")
    action_steps: List[str] = Field(default=[], description="Specific steps to take")
    reasoning: str = Field(..., description="Why this recommendation is made")
    category: Optional[str] = None
    amount: Optional[Decimal] = None
    deadline: Optional[date] = None
    is_completed: bool = False
    created_at: datetime
    expires_at: Optional[datetime] = None

class InvestmentReadinessScore(BaseModel):
    """Investment readiness assessment"""
    overall_score: int = Field(..., ge=0, le=100)
    readiness_level: InvestmentReadinessLevel
    component_scores: Dict[str, int] = Field(..., description="Breakdown of score components")
    strengths: List[str] = Field(default=[], description="Financial strengths")
    weaknesses: List[str] = Field(default=[], description="Areas to improve")
    recommendations: List[str] = Field(default=[], description="Steps to improve readiness")
    risk_tolerance: RiskTolerance
    recommended_allocation: Dict[str, float] = Field(..., description="Suggested portfolio allocation")
    minimum_investment_amount: Decimal
    emergency_fund_status: str = Field(..., pattern=r'^(none|insufficient|adequate|excellent)$')
    debt_to_income_ratio: float
    cash_flow_stability: int = Field(..., ge=0, le=100)
    last_calculated: datetime

class MLInsight(BaseModel):
    """ML-based financial insight"""
    id: str
    insight_type: str = Field(..., pattern=r'^(spending_pattern|income_trend|savings_opportunity|risk_alert|behavioral_nudge)$')
    title: str
    description: str
    confidence_score: float = Field(..., ge=0, le=1, description="ML model confidence")
    data_points: Dict[str, Any] = Field(default={}, description="Supporting data")
    predicted_outcome: Optional[str] = None
    recommendation: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[Decimal] = None
    trend: Optional[str] = Field(None, pattern=r'^(increasing|decreasing|stable|volatile)$')
    created_at: datetime

class FinancialPersonaProfile(BaseModel):
    """User's financial persona and behavior profile"""
    persona: FinancialPersona
    confidence: float = Field(..., ge=0, le=1)
    characteristics: List[str]
    spending_habits: Dict[str, Any]
    savings_habits: Dict[str, Any]
    investment_behavior: Dict[str, Any]
    financial_goals_alignment: int = Field(..., ge=0, le=100)
    behavior_trends: List[str]
    last_updated: datetime

class AIGuidanceResponse(BaseModel):
    """Complete AI guidance response"""
    user_id: str
    recommendations: List[PersonalizedRecommendation]
    investment_readiness: InvestmentReadinessScore
    ml_insights: List[MLInsight]
    financial_persona: FinancialPersonaProfile
    overall_financial_health: int = Field(..., ge=0, le=100)
    next_review_date: date
    generated_at: datetime

# Settings Models
class AIGuidanceSettings(BaseModel):
    """User settings for AI guidance"""
    user_id: str
    enabled: bool = True
    recommendation_frequency: str = Field(default="weekly", pattern=r'^(daily|weekly|monthly)$')
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    investment_goals: List[str] = Field(default=[])
    exclude_recommendation_types: List[RecommendationType] = Field(default=[])
    min_recommendation_priority: RecommendationPriority = RecommendationPriority.MEDIUM
    enable_ml_insights: bool = True
    enable_behavioral_nudges: bool = True
    updated_at: datetime

