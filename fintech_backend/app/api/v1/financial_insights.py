"""
Financial Insights API Endpoints

Merged module combining:
  - AI Financial Guidance  (was ai_guidance.py)   → /insights/ai-guidance/*
  - Financial Health Score (was financial_health.py) → /insights/health/*

Both compute a score out of 100 with recommendations as output.
They live here together under the /insights prefix.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ...database.config import get_db
from ...core.auth import get_current_user
from app.database import get_db as get_db_alt  # financial_health used a different import path

# ── AI Guidance models & service ────────────────────────────────────────────
from ...models.auth import UserProfile
from ...models.ai_guidance import (
    AIGuidanceRequest, AIGuidanceResponse, PersonalizedRecommendation,
    InvestmentReadinessScore, MLInsight, AIGuidanceSettings,
    RecommendationType, RecommendationPriority, RiskTolerance
)
from ...services.ai_guidance_service import AIGuidanceService

# ── Financial Health models & service ───────────────────────────────────────
from ...models.financial_health import (
    FinancialHealthScore,
    HealthScoreHistory,
    HealthScoreSettings
)
from ...services.financial_health_service import FinancialHealthService

router = APIRouter(prefix="/insights", tags=["Financial Insights"])


# ═══════════════════════════════════════════════════════════════════════════
# AI GUIDANCE  (/insights/ai-guidance/*)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/ai-guidance/", response_model=AIGuidanceResponse)
async def get_ai_guidance(
    include_recommendations: bool = True,
    include_investment_readiness: bool = True,
    include_insights: bool = True,
    time_horizon_days: int = 90,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive AI financial guidance.

    Returns personalized recommendations, investment readiness score,
    ML-based insights, and financial persona analysis.
    """
    try:
        service = AIGuidanceService(db)
        request = AIGuidanceRequest(
            include_recommendations=include_recommendations,
            include_investment_readiness=include_investment_readiness,
            include_insights=include_insights,
            time_horizon_days=time_horizon_days
        )
        return await service.get_ai_guidance(current_user.user_id, request)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to generate AI guidance: {str(e)}")


@router.get("/ai-guidance/recommendations", response_model=List[PersonalizedRecommendation])
async def get_recommendations(
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get personalized financial recommendations."""
    try:
        service = AIGuidanceService(db)
        settings = await service._get_user_settings(current_user.user_id)
        return await service.generate_recommendations(current_user.user_id, settings)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to generate recommendations: {str(e)}")


@router.get("/ai-guidance/investment-readiness", response_model=InvestmentReadinessScore)
async def get_investment_readiness(
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Calculate investment readiness score (0-100)."""
    try:
        service = AIGuidanceService(db)
        settings = await service._get_user_settings(current_user.user_id)
        return await service.calculate_investment_readiness(current_user.user_id, settings)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to calculate investment readiness: {str(e)}")


@router.get("/ai-guidance/insights", response_model=List[MLInsight])
async def get_ml_insights(
    time_horizon_days: int = 90,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get ML-based financial insights."""
    try:
        service = AIGuidanceService(db)
        return await service.generate_ml_insights(current_user.user_id, time_horizon_days)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to generate insights: {str(e)}")


@router.get("/ai-guidance/settings", response_model=AIGuidanceSettings)
async def get_ai_settings(
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get AI guidance settings."""
    try:
        service = AIGuidanceService(db)
        return await service._get_user_settings(current_user.user_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to get settings: {str(e)}")


@router.put("/ai-guidance/settings", response_model=AIGuidanceSettings)
async def update_ai_settings(
    risk_tolerance: Optional[RiskTolerance] = None,
    recommendation_frequency: Optional[str] = None,
    min_recommendation_priority: Optional[RecommendationPriority] = None,
    enable_ml_insights: Optional[bool] = None,
    enable_behavioral_nudges: Optional[bool] = None,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update AI guidance settings."""
    try:
        service = AIGuidanceService(db)
        settings = await service._get_user_settings(current_user.user_id)
        if risk_tolerance is not None:
            settings.risk_tolerance = risk_tolerance
        if recommendation_frequency is not None:
            settings.recommendation_frequency = recommendation_frequency
        if min_recommendation_priority is not None:
            settings.min_recommendation_priority = min_recommendation_priority
        if enable_ml_insights is not None:
            settings.enable_ml_insights = enable_ml_insights
        if enable_behavioral_nudges is not None:
            settings.enable_behavioral_nudges = enable_behavioral_nudges
        settings.updated_at = datetime.utcnow()
        service.settings_cache[current_user.user_id] = settings
        return settings
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to update settings: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════
# FINANCIAL HEALTH  (/insights/health/*)
# ═══════════════════════════════════════════════════════════════════════════

_MOCK_FINANCIAL_DATA = {
    'monthly_income': 6000, 'monthly_expenses': 3500, 'monthly_savings': 1200,
    'monthly_debt_payment': 800, 'emergency_fund': 12000, 'total_debt': 25000,
    'total_investments': 45000, 'budget_adherence': 85, 'income_growth_rate': 5.5,
    'income_stability': 90, 'portfolio_diversification': 70
}


@router.get("/health/score", response_model=FinancialHealthScore)
async def get_health_score(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current financial health score (0-100) with component breakdown,
    trend analysis, and personalized recommendations.
    """
    try:
        service = FinancialHealthService(db)
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user['user_id']
        return await service.calculate_health_score(user_id=user_id, financial_data=_MOCK_FINANCIAL_DATA)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating health score: {str(e)}")


@router.get("/health/history", response_model=HealthScoreHistory)
async def get_health_score_history(
    days: int = Query(default=90, ge=7, le=365),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get historical health score data."""
    try:
        service = FinancialHealthService(db)
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user['user_id']
        return await service.get_score_history(user_id=user_id, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching score history: {str(e)}")


@router.get("/health/settings", response_model=HealthScoreSettings)
async def get_health_settings(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's health score calculation settings."""
    try:
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user['user_id']
        return HealthScoreSettings(
            user_id=user_id,
            custom_weights=None,
            excluded_factors=[],
            notification_threshold=5.0,
            auto_update_frequency="daily"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching settings: {str(e)}")


@router.put("/health/settings", response_model=HealthScoreSettings)
async def update_health_settings(
    settings: HealthScoreSettings,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's health score calculation settings."""
    try:
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user['user_id']
        if settings.user_id != user_id:
            raise HTTPException(status_code=403, detail="Cannot update settings for another user")
        return settings
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating settings: {str(e)}")


@router.post("/health/recalculate", response_model=FinancialHealthScore)
async def recalculate_health_score(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Force recalculation of health score with latest financial data."""
    try:
        service = FinancialHealthService(db)
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user['user_id']
        return await service.calculate_health_score(user_id=user_id, financial_data=_MOCK_FINANCIAL_DATA)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recalculating score: {str(e)}")
