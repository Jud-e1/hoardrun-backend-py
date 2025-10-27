from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..models.analytics import (
    AnalyticsRequest, BudgetRequest, SpendingAnalysisRequest, FinancialGoalRequest,
    SpendingByCategory, BudgetProfile, BudgetSummary, FinancialInsight,
    CashFlowAnalysis, FinancialHealthScore, FinancialGoalProfile, FinancialAlert,
    AnalyticsPeriod, TransactionCategory
)
from ..services.analytics_service import AnalyticsService
from ..core.exceptions import NotFoundError, ValidationError, BusinessLogicError
from ..config.logging import get_logger
from ..database.config import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])

def get_analytics_service(db: Session = Depends(get_db)) -> AnalyticsService:
    """Dependency to get analytics service instance with database session."""
    return AnalyticsService(db)

@router.post("/spending-analysis", response_model=List[SpendingByCategory])
async def get_spending_analysis(
    request: SpendingAnalysisRequest,
    current_user: dict = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get detailed spending analysis by category.

    - **period**: Analysis period (daily, weekly, monthly, quarterly, yearly, custom)
    - **start_date**: Start date for custom period analysis
    - **end_date**: End date for custom period analysis
    - **group_by**: Group spending by (category, merchant, day, week, month)
    - **currency**: Currency for analysis (default: UGX)

    Returns spending breakdown with:
    - Amount and percentage per category
    - Transaction counts and averages
    - Spending trends and comparisons
    """
    try:
        analysis = await analytics_service.get_spending_analysis(
            user_id=current_user["user_id"],
            request=request
        )
        return analysis
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve spending analysis: {str(e)}"
        )

@router.post("/cash-flow", response_model=CashFlowAnalysis)
async def get_cash_flow_analysis(
    request: AnalyticsRequest,
    current_user: dict = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get cash flow analysis for a specified period.

    - **period**: Analysis period (daily, weekly, monthly, quarterly, yearly, custom)
    - **start_date**: Start date for analysis
    - **end_date**: End date for analysis
    - **categories**: Filter by specific transaction categories
    - **currency**: Currency for analysis (default: UGX)

    Returns comprehensive cash flow data:
    - Total income vs expenses
    - Net cash flow and trends
    - Income sources breakdown
    - Expense categories breakdown
    """
    try:
        cash_flow = await analytics_service.get_cash_flow_analysis(
            user_id=current_user["user_id"],
            request=request
        )
        return cash_flow
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cash flow analysis: {str(e)}"
        )

@router.post("/budgets", response_model=BudgetProfile, status_code=status.HTTP_201_CREATED)
async def create_budget(
    request: BudgetRequest,
    current_user: dict = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Create a new budget for expense tracking.

    - **name**: Budget name (1-100 characters)
    - **category**: Transaction category to track
    - **amount**: Budget amount (must be positive)
    - **period**: Budget period (daily, weekly, monthly, quarterly, yearly)
    - **start_date**: Budget start date
    - **end_date**: Budget end date (optional)
    - **currency**: Budget currency (default: UGX)
    - **is_active**: Whether budget is active

    Returns the created budget with current spending status.
    """
    try:
        budget = await analytics_service.create_budget(
            user_id=current_user["user_id"],
            request=request
        )
        return budget
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create budget: {str(e)}"
        )

@router.get("/budgets", response_model=List[BudgetProfile])
async def get_user_budgets(
    current_user: dict = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get all budgets for the current user.

    Returns all user budgets with:
    - Budget details and limits
    - Current spending amounts
    - Remaining budget and percentages
    - Budget status and recommendations
    """
    try:
        budgets = await analytics_service.get_user_budgets(
            user_id=current_user["user_id"]
        )
        return budgets
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve budgets: {str(e)}"
        )

@router.get("/budgets/summary", response_model=BudgetSummary)
async def get_budget_summary(
    current_user: dict = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get budget summary and overview.

    Returns comprehensive budget overview:
    - Total budgets and active count
    - Total budgeted vs spent amounts
    - Budget performance statistics
    - Budgets over limit, on track, and under budget
    """
    try:
        summary = await analytics_service.get_budget_summary(
            user_id=current_user["user_id"]
        )
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve budget summary: {str(e)}"
        )

@router.post("/financial-goals", response_model=FinancialGoalProfile, status_code=status.HTTP_201_CREATED)
async def create_financial_goal(
    request: FinancialGoalRequest,
    current_user: dict = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Create a new financial goal.

    - **name**: Goal name (1-100 characters)
    - **target_amount**: Target amount to achieve (must be positive)
    - **target_date**: Target completion date
    - **category**: Goal category (savings, transportation, etc.)
    - **currency**: Goal currency (default: UGX)
    - **description**: Optional goal description (max 500 characters)

    Returns the created goal with progress tracking information.
    """
    try:
        goal = await analytics_service.create_financial_goal(
            user_id=current_user["user_id"],
            request=request
        )
        return goal
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create financial goal: {str(e)}"
        )

@router.get("/financial-goals", response_model=List[FinancialGoalProfile])
async def get_user_financial_goals(
    current_user: dict = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get all financial goals for the current user.

    Returns all user financial goals with:
    - Goal details and targets
    - Current progress and remaining amounts
    - Timeline and monthly targets
    - On-track status and recommendations
    """
    try:
        goals = await analytics_service.get_user_financial_goals(
            user_id=current_user["user_id"]
        )
        return goals
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve financial goals: {str(e)}"
        )

@router.get("/financial-health", response_model=FinancialHealthScore)
async def get_financial_health_score(
    current_user: dict = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get comprehensive financial health score.

    Returns detailed financial health assessment:
    - Overall financial health score (0-100)
    - Component scores (spending, savings, budget adherence, etc.)
    - Personalized recommendations for improvement
    - Score breakdown and explanations
    """
    try:
        health_score = await analytics_service.get_financial_health_score(
            user_id=current_user["user_id"]
        )
        return health_score
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate financial health score: {str(e)}"
        )

@router.get("/insights", response_model=List[FinancialInsight])
async def get_financial_insights(
    current_user: dict = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get personalized financial insights and recommendations.

    Returns AI-powered financial insights:
    - Spending pattern analysis
    - Budget performance alerts
    - Saving opportunities
    - Actionable recommendations with priority levels
    """
    try:
        insights = await analytics_service.get_financial_insights(
            user_id=current_user["user_id"]
        )
        return insights
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve financial insights: {str(e)}"
        )

@router.get("/alerts", response_model=List[FinancialAlert])
async def get_financial_alerts(
    current_user: dict = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get financial alerts and notifications.

    Returns active financial alerts:
    - Budget exceeded alerts
    - Unusual spending notifications
    - Large transaction alerts
    - Goal milestone notifications
    - Low balance warnings
    """
    try:
        alerts = await analytics_service.get_user_financial_alerts(
            user_id=current_user["user_id"]
        )
        return alerts
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve financial alerts: {str(e)}"
        )

@router.get("/health", response_model=Dict[str, Any])
async def get_analytics_health(
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get analytics service health status.

    Returns service health metrics including:
    - Total budgets and financial goals
    - Active alerts and processing metrics
    - Feature availability status
    - Service version information
    """
    try:
        health_status = await analytics_service.get_health_status()
        return health_status
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve health status: {str(e)}"
        )
