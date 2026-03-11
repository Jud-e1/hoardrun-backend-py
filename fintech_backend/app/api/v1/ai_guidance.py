"""
AI Financial Guidance API Endpoints
Provides personalized financial recommendations and investment readiness scoring
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from ...core.database import get_db
from ...core.auth import get_current_user
from ...models.auth import UserProfile
from ...models.ai_guidance import (
    AIGuidanceRequest, AIGuidanceResponse, PersonalizedRecommendation,
    InvestmentReadinessScore, MLInsight, AIGuidanceSettings,
    RecommendationType, RecommendationPriority, RiskTolerance
)
from ...services.ai_guidance_service import AIGuidanceService

router = APIRouter(prefix="/ai-guidance", tags=["AI Guidance"])


@router.get("/", response_model=AIGuidanceResponse)
async def get_ai_guidance(
    include_recommendations: bool = True,
    include_investment_readiness: bool = True,
    include_insights: bool = True,
    time_horizon_days: int = 90,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive AI financial guidance
    
    Returns personalized recommendations, investment readiness score,
    ML-based insights, and financial persona analysis.
    
    **Features:**
    - Personalized action recommendations
    - Investment readiness scoring
    - ML-based behavioral insights
    - Financial persona identification
    - Risk-adjusted portfolio suggestions
    """
    try:
        service = AIGuidanceService(db)
        request = AIGuidanceRequest(
            include_recommendations=include_recommendations,
            include_investment_readiness=include_investment_readiness,
            include_insights=include_insights,
            time_horizon_days=time_horizon_days
        )
        
        guidance = await service.get_ai_guidance(current_user.user_id, request)
        return guidance
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate AI guidance: {str(e)}"
        )


@router.get("/recommendations", response_model=List[PersonalizedRecommendation])
async def get_recommendations(
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized financial recommendations
    
    Returns actionable recommendations based on:
    - Current financial health
    - Spending patterns
    - Savings behavior
    - Cash flow analysis
    - Goal progress
    """
    try:
        service = AIGuidanceService(db)
        settings = await service._get_user_settings(current_user.user_id)
        recommendations = await service.generate_recommendations(current_user.user_id, settings)
        return recommendations
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {str(e)}"
        )


@router.get("/investment-readiness", response_model=InvestmentReadinessScore)
async def get_investment_readiness(
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Calculate investment readiness score
    
    Analyzes:
    - Emergency fund status
    - Cash flow stability
    - Debt management
    - Savings rate
    - Financial discipline
    
    Returns:
    - Overall readiness score (0-100)
    - Component breakdown
    - Recommended portfolio allocation
    - Strengths and weaknesses
    - Action steps to improve readiness
    """
    try:
        service = AIGuidanceService(db)
        settings = await service._get_user_settings(current_user.user_id)
        readiness = await service.calculate_investment_readiness(current_user.user_id, settings)
        return readiness
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate investment readiness: {str(e)}"
        )


@router.get("/insights", response_model=List[MLInsight])
async def get_ml_insights(
    time_horizon_days: int = 90,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get ML-based financial insights
    
    Analyzes transaction patterns to identify:
    - Spending patterns and anomalies
    - Income trends
    - Savings opportunities
    - Risk alerts
    - Behavioral patterns
    """
    try:
        service = AIGuidanceService(db)
        insights = await service.generate_ml_insights(current_user.user_id, time_horizon_days)
        return insights
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate insights: {str(e)}"
        )


@router.get("/settings", response_model=AIGuidanceSettings)
async def get_settings(
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get AI guidance settings for the user"""
    try:
        service = AIGuidanceService(db)
        settings = await service._get_user_settings(current_user.user_id)
        return settings
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get settings: {str(e)}"
        )


@router.put("/settings", response_model=AIGuidanceSettings)
async def update_settings(
    risk_tolerance: RiskTolerance = None,
    recommendation_frequency: str = None,
    min_recommendation_priority: RecommendationPriority = None,
    enable_ml_insights: bool = None,
    enable_behavioral_nudges: bool = None,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update AI guidance settings
    
    Customize:
    - Risk tolerance (conservative/moderate/aggressive)
    - Recommendation frequency (daily/weekly/monthly)
    - Minimum priority level
    - ML insights toggle
    - Behavioral nudges toggle
    """
    try:
        service = AIGuidanceService(db)
        settings = await service._get_user_settings(current_user.user_id)
        
        # Update settings
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )

