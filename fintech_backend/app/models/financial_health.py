"""
Financial Health Score Models

Comprehensive models for tracking and analyzing user financial health.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator


class HealthScoreLevel(str, Enum):
    """Financial health score levels"""
    CRITICAL = "critical"  # 0-40
    POOR = "poor"  # 41-60
    FAIR = "fair"  # 61-75
    GOOD = "good"  # 76-85
    EXCELLENT = "excellent"  # 86-100


class FactorCategory(str, Enum):
    """Categories of financial health factors"""
    SAVINGS = "savings"
    DEBT = "debt"
    SPENDING = "spending"
    INCOME = "income"
    EMERGENCY_FUND = "emergency_fund"
    INVESTMENTS = "investments"


class TrendDirection(str, Enum):
    """Trend direction for score changes"""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


class HealthFactor(BaseModel):
    """Individual factor contributing to financial health"""
    category: FactorCategory
    name: str
    score: float = Field(..., ge=0, le=100, description="Factor score (0-100)")
    weight: float = Field(..., ge=0, le=1, description="Weight in overall score")
    current_value: float
    target_value: Optional[float] = None
    unit: str = Field(default="", description="Unit of measurement (%, $, etc.)")
    status: HealthScoreLevel
    description: str
    impact: str = Field(..., description="How this factor impacts overall health")
    
    class Config:
        use_enum_values = True


class ScoreImprovement(BaseModel):
    """Recommendation for improving financial health score"""
    factor: FactorCategory
    title: str
    description: str
    potential_impact: float = Field(..., ge=0, le=100, description="Potential score increase")
    difficulty: str = Field(..., description="easy, medium, hard")
    timeframe: str = Field(..., description="Expected time to see results")
    action_steps: List[str]
    priority: int = Field(..., ge=1, le=5, description="Priority level (1=highest)")
    
    class Config:
        use_enum_values = True


class HealthScoreTrend(BaseModel):
    """Historical trend data for health score"""
    date: datetime
    score: float = Field(..., ge=0, le=100)
    level: HealthScoreLevel
    factors: Dict[str, float] = Field(default_factory=dict, description="Factor scores at this point")
    
    class Config:
        use_enum_values = True


class FinancialHealthScore(BaseModel):
    """Complete financial health score assessment"""
    user_id: str
    overall_score: float = Field(..., ge=0, le=100, description="Overall health score (0-100)")
    level: HealthScoreLevel
    factors: List[HealthFactor]
    trend_direction: TrendDirection
    score_change_30d: float = Field(default=0.0, description="Score change over last 30 days")
    score_change_90d: float = Field(default=0.0, description="Score change over last 90 days")
    percentile: Optional[float] = Field(None, ge=0, le=100, description="User's percentile vs others")
    
    # Strengths and weaknesses
    top_strengths: List[str] = Field(default_factory=list, description="Top 3 financial strengths")
    areas_for_improvement: List[str] = Field(default_factory=list, description="Top 3 areas to improve")
    
    # Recommendations
    improvements: List[ScoreImprovement] = Field(default_factory=list, description="Prioritized improvements")
    
    # Metadata
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    next_update: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
    
    @validator('level', pre=True, always=True)
    def determine_level(cls, v, values):
        """Automatically determine level based on score"""
        if 'overall_score' not in values:
            return v
        
        score = values['overall_score']
        if score >= 86:
            return HealthScoreLevel.EXCELLENT
        elif score >= 76:
            return HealthScoreLevel.GOOD
        elif score >= 61:
            return HealthScoreLevel.FAIR
        elif score >= 41:
            return HealthScoreLevel.POOR
        else:
            return HealthScoreLevel.CRITICAL


class HealthScoreHistory(BaseModel):
    """Historical health score data"""
    user_id: str
    trends: List[HealthScoreTrend]
    period_start: datetime
    period_end: datetime
    average_score: float = Field(..., ge=0, le=100)
    highest_score: float = Field(..., ge=0, le=100)
    lowest_score: float = Field(..., ge=0, le=100)
    
    class Config:
        use_enum_values = True


class HealthScoreSettings(BaseModel):
    """User preferences for health score calculation"""
    user_id: str
    custom_weights: Optional[Dict[str, float]] = Field(
        None,
        description="Custom factor weights (overrides defaults)"
    )
    excluded_factors: List[FactorCategory] = Field(
        default_factory=list,
        description="Factors to exclude from calculation"
    )
    notification_threshold: float = Field(
        default=5.0,
        ge=0,
        le=100,
        description="Notify when score changes by this amount"
    )
    auto_update_frequency: str = Field(
        default="daily",
        description="How often to recalculate: daily, weekly, monthly"
    )
    
    class Config:
        use_enum_values = True

