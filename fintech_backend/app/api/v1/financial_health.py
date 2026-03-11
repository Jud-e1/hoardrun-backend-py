"""
Financial Health Score API Endpoints

REST API for accessing and managing financial health scores.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.financial_health import (
    FinancialHealthScore,
    HealthScoreHistory,
    HealthScoreSettings
)
from app.services.financial_health_service import FinancialHealthService
from app.core.auth import get_current_user

router = APIRouter(prefix="/financial-health", tags=["financial-health"])


@router.get("/score", response_model=FinancialHealthScore)
async def get_health_score(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current financial health score for the authenticated user.
    
    Returns comprehensive health assessment including:
    - Overall score (0-100)
    - Individual factor scores
    - Trend analysis
    - Personalized recommendations
    """
    try:
        service = FinancialHealthService(db)
        
        # TODO: Fetch actual financial data from database
        # For now, using mock data
        financial_data = {
            'monthly_income': 6000,
            'monthly_expenses': 3500,
            'monthly_savings': 1200,
            'monthly_debt_payment': 800,
            'emergency_fund': 12000,
            'total_debt': 25000,
            'total_investments': 45000,
            'budget_adherence': 85,
            'income_growth_rate': 5.5,
            'income_stability': 90,
            'portfolio_diversification': 70
        }
        
        score = await service.calculate_health_score(
            user_id=current_user['user_id'],
            financial_data=financial_data
        )
        
        return score
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating health score: {str(e)}")


@router.get("/history", response_model=HealthScoreHistory)
async def get_score_history(
    days: int = Query(default=90, ge=7, le=365, description="Number of days of history"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get historical health score data.
    
    Args:
        days: Number of days of history to retrieve (7-365)
        
    Returns:
        Historical trends, average, highest, and lowest scores
    """
    try:
        service = FinancialHealthService(db)
        
        history = await service.get_score_history(
            user_id=current_user['user_id'],
            days=days
        )
        
        return history
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching score history: {str(e)}")


@router.get("/settings", response_model=HealthScoreSettings)
async def get_score_settings(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's health score calculation settings.
    
    Returns custom weights, excluded factors, and notification preferences.
    """
    try:
        # TODO: Fetch from database
        # For now, return default settings
        return HealthScoreSettings(
            user_id=current_user['user_id'],
            custom_weights=None,
            excluded_factors=[],
            notification_threshold=5.0,
            auto_update_frequency="daily"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching settings: {str(e)}")


@router.put("/settings", response_model=HealthScoreSettings)
async def update_score_settings(
    settings: HealthScoreSettings,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user's health score calculation settings.
    
    Allows customization of:
    - Factor weights
    - Excluded factors
    - Notification thresholds
    - Update frequency
    """
    try:
        # Validate user_id matches
        if settings.user_id != current_user['user_id']:
            raise HTTPException(status_code=403, detail="Cannot update settings for another user")
        
        # TODO: Save to database
        # For now, just return the settings
        return settings
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating settings: {str(e)}")


@router.post("/recalculate", response_model=FinancialHealthScore)
async def recalculate_score(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Force recalculation of health score with latest financial data.
    
    Useful after major financial changes or account updates.
    """
    try:
        service = FinancialHealthService(db)
        
        # TODO: Fetch latest financial data
        financial_data = {
            'monthly_income': 6000,
            'monthly_expenses': 3500,
            'monthly_savings': 1200,
            'monthly_debt_payment': 800,
            'emergency_fund': 12000,
            'total_debt': 25000,
            'total_investments': 45000,
            'budget_adherence': 85,
            'income_growth_rate': 5.5,
            'income_stability': 90,
            'portfolio_diversification': 70
        }
        
        score = await service.calculate_health_score(
            user_id=current_user['user_id'],
            financial_data=financial_data
        )
        
        # TODO: Save to database
        
        return score
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recalculating score: {str(e)}")

