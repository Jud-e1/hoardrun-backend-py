"""
Savings Management API Routes
Handles savings goals, contributions, and savings account management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer
from decimal import Decimal

from ...core.auth import get_current_user
from ...models.savings import (
    SavingsGoalCreateRequest,
    SavingsGoalUpdateRequest,
    ContributionRequest,
    SavingsGoalProfile,
    ContributionProfile,
    SavingsGoalHistory,
    SavingsGoalStats,
    SavingsInsights,
    AutoSaveSettings,
    SavingsGoalStatus,
    FixedDepositCreateRequest,
    FixedDepositProfile,
    AutomatedSavingCreateRequest,
    AutomatedSavingProfile,
    FixedDepositTerm,
    FixedDepositStatus,
    AutomatedSavingFrequency,
    AutomatedSavingStatus,
    SavingsGoalType
)
from ...models.base import BaseResponse, PaginatedResponse
from ...services.savings_service import SavingsService
from ...core.exceptions import ValidationError, NotFoundError, ConflictError

router = APIRouter(prefix="/savings", tags=["Savings"])
security = HTTPBearer()

# Initialize service
savings_service = SavingsService()

@router.get(
    "/goals",
    response_model=PaginatedResponse[SavingsGoalProfile],
    summary="Get Savings Goals",
    description="Retrieve user's savings goals with filtering and pagination"
)
async def get_savings_goals(
    current_user: dict = Depends(get_current_user),
    status: Optional[SavingsGoalStatus] = Query(None, description="Filter by goal status"),
    goal_type: Optional[SavingsGoalType] = Query(None, description="Filter by goal type"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page")
):
    """
    Get user's savings goals with optional filtering.
    
    Supports filtering by:
    - Goal status (active, paused, completed, cancelled)
    - Goal type (emergency_fund, vacation, home_purchase, etc.)
    - Pagination for large lists
    """
    try:
        result = await savings_service.get_user_savings_goals(
            user_id=current_user["user_id"],
            status=status,
            goal_type=goal_type,
            page=page,
            limit=limit
        )
        
        return PaginatedResponse(
            success=True,
            message="Savings goals retrieved successfully",
            data=result["items"],
            total=result["total"],
            page=page,
            limit=limit,
            total_pages=result["total_pages"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve savings goals: {str(e)}"
        )

@router.post(
    "/goals",
    response_model=BaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Savings Goal",
    description="Create a new savings goal"
)
async def create_savings_goal(
    goal_data: SavingsGoalCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new savings goal.
    
    Features:
    - Multiple goal types (emergency fund, vacation, home purchase, etc.)
    - Optional target dates and automatic contributions
    - Auto-save rules (round up, percentage, fixed amount)
    - Privacy settings
    """
    try:
        # Check if user has reached goal limit
        existing_count = await savings_service.get_user_goals_count(
            user_id=current_user["user_id"]
        )
        
        if existing_count >= 20:  # Maximum 20 goals per user
            raise ConflictError("Maximum number of savings goals reached (20)")
        
        # Create the savings goal
        savings_goal = await savings_service.create_savings_goal(
            user_id=current_user["user_id"],
            goal_data=goal_data
        )
        
        return BaseResponse(
            success=True,
            message="Savings goal created successfully",
            data=savings_goal
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create savings goal: {str(e)}"
        )

@router.get(
    "/goals/{goal_id}",
    response_model=BaseResponse,
    summary="Get Savings Goal",
    description="Get a specific savings goal by ID"
)
async def get_savings_goal(
    goal_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific savings goal by ID.
    
    Returns detailed information including:
    - Current progress and statistics
    - Contribution history summary
    - Next scheduled contribution
    - Auto-save settings
    """
    try:
        savings_goal = await savings_service.get_savings_goal_by_id(
            goal_id=goal_id,
            user_id=current_user["user_id"]
        )
        
        if not savings_goal:
            raise NotFoundError("Savings goal not found")
        
        return BaseResponse(
            success=True,
            message="Savings goal retrieved successfully",
            data=savings_goal
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve savings goal: {str(e)}"
        )

@router.put(
    "/goals/{goal_id}",
    response_model=BaseResponse,
    summary="Update Savings Goal",
    description="Update an existing savings goal"
)
async def update_savings_goal(
    goal_id: str,
    goal_data: SavingsGoalUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update an existing savings goal.
    
    Allows updating:
    - Goal name and description
    - Target amount and date
    - Auto-contribution settings
    - Auto-save rules
    - Goal status (pause, resume, cancel)
    """
    try:
        # Verify goal belongs to user
        existing_goal = await savings_service.get_savings_goal_by_id(
            goal_id=goal_id,
            user_id=current_user["user_id"]
        )
        
        if not existing_goal:
            raise NotFoundError("Savings goal not found")
        
        # Update the savings goal
        updated_goal = await savings_service.update_savings_goal(
            goal_id=goal_id,
            user_id=current_user["user_id"],
            goal_data=goal_data
        )
        
        return BaseResponse(
            success=True,
            message="Savings goal updated successfully",
            data=updated_goal
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update savings goal: {str(e)}"
        )

@router.delete(
    "/goals/{goal_id}",
    response_model=BaseResponse,
    summary="Delete Savings Goal",
    description="Delete a savings goal"
)
async def delete_savings_goal(
    goal_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a savings goal.
    
    Notes:
    - Cannot delete goals with active contributions
    - Funds will be transferred to default savings account
    - Action is irreversible
    """
    try:
        # Verify goal belongs to user
        existing_goal = await savings_service.get_savings_goal_by_id(
            goal_id=goal_id,
            user_id=current_user["user_id"]
        )
        
        if not existing_goal:
            raise NotFoundError("Savings goal not found")
        
        # Check if goal can be deleted
        if existing_goal.current_amount > 0:
            raise ConflictError("Cannot delete goal with existing funds. Please withdraw funds first.")
        
        # Delete the savings goal
        await savings_service.delete_savings_goal(
            goal_id=goal_id,
            user_id=current_user["user_id"]
        )
        
        return BaseResponse(
            success=True,
            message="Savings goal deleted successfully",
            data={"goal_id": goal_id}
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete savings goal: {str(e)}"
        )

@router.post(
    "/goals/{goal_id}/contribute",
    response_model=BaseResponse,
    summary="Add to Savings Goal",
    description="Make a contribution to a savings goal"
)
async def contribute_to_goal(
    goal_id: str,
    contribution_data: ContributionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Make a contribution to a savings goal.
    
    Features:
    - One-time or recurring contributions
    - Multiple payment methods supported
    - Optional contribution notes
    - Automatic goal completion detection
    """
    try:
        # Verify goal belongs to user and is active
        existing_goal = await savings_service.get_savings_goal_by_id(
            goal_id=goal_id,
            user_id=current_user["user_id"]
        )
        
        if not existing_goal:
            raise NotFoundError("Savings goal not found")
        
        if existing_goal.status not in [SavingsGoalStatus.ACTIVE]:
            raise ConflictError("Cannot contribute to inactive goal")
        
        # Make the contribution
        contribution = await savings_service.make_contribution(
            goal_id=goal_id,
            user_id=current_user["user_id"],
            contribution_data=contribution_data
        )
        
        return BaseResponse(
            success=True,
            message="Contribution added successfully",
            data=contribution
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to make contribution: {str(e)}"
        )

@router.get(
    "/goals/{goal_id}/history",
    response_model=PaginatedResponse[SavingsGoalHistory],
    summary="Get Savings Goal History",
    description="Get contribution and activity history for a savings goal"
)
async def get_goal_history(
    goal_id: str,
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    Get contribution and activity history for a savings goal.
    
    Includes:
    - All contributions with dates and amounts
    - Goal modifications and status changes
    - Auto-save activities
    - Milestone achievements
    """
    try:
        # Verify goal belongs to user
        existing_goal = await savings_service.get_savings_goal_by_id(
            goal_id=goal_id,
            user_id=current_user["user_id"]
        )
        
        if not existing_goal:
            raise NotFoundError("Savings goal not found")
        
        # Get goal history
        result = await savings_service.get_goal_history(
            goal_id=goal_id,
            user_id=current_user["user_id"],
            page=page,
            limit=limit
        )
        
        return PaginatedResponse(
            success=True,
            message="Goal history retrieved successfully",
            data=result["items"],
            total=result["total"],
            page=page,
            limit=limit,
            total_pages=result["total_pages"]
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve goal history: {str(e)}"
        )

@router.get(
    "/stats",
    response_model=BaseResponse,
    summary="Get Savings Statistics",
    description="Get comprehensive savings statistics for the user"
)
async def get_savings_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    Get comprehensive savings statistics.
    
    Includes:
    - Total goals and completion rates
    - Total amount saved and targets
    - Average progress across goals
    - Monthly savings rate
    - Most successful goal types
    """
    try:
        stats = await savings_service.get_savings_statistics(
            user_id=current_user["user_id"]
        )
        
        return BaseResponse(
            success=True,
            message="Savings statistics retrieved successfully",
            data=stats
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve savings statistics: {str(e)}"
        )

@router.get(
    "/insights",
    response_model=BaseResponse,
    summary="Get Savings Insights",
    description="Get personalized savings insights and recommendations"
)
async def get_savings_insights(
    current_user: dict = Depends(get_current_user)
):
    """
    Get personalized savings insights and recommendations.
    
    Provides:
    - Current vs recommended savings rate
    - Projected completion dates
    - Savings streak tracking
    - Performance analysis
    - Personalized recommendations
    - Seasonal trends
    """
    try:
        insights = await savings_service.get_savings_insights(
            user_id=current_user["user_id"]
        )
        
        return BaseResponse(
            success=True,
            message="Savings insights retrieved successfully",
            data=insights
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve savings insights: {str(e)}"
        )

@router.get(
    "/auto-save/settings",
    response_model=BaseResponse,
    summary="Get Auto-Save Settings",
    description="Get user's auto-save settings"
)
async def get_auto_save_settings(
    current_user: dict = Depends(get_current_user)
):
    """
    Get user's auto-save settings.
    
    Includes:
    - Round-up rules and multipliers
    - Percentage-based saving
    - Fixed amount saving
    - Balance limits and restrictions
    """
    try:
        settings = await savings_service.get_auto_save_settings(
            user_id=current_user["user_id"]
        )
        
        return BaseResponse(
            success=True,
            message="Auto-save settings retrieved successfully",
            data=settings
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve auto-save settings: {str(e)}"
        )

@router.put(
    "/auto-save/settings",
    response_model=BaseResponse,
    summary="Update Auto-Save Settings",
    description="Update user's auto-save settings"
)
async def update_auto_save_settings(
    settings_data: AutoSaveSettings,
    current_user: dict = Depends(get_current_user)
):
    """
    Update user's auto-save settings.
    
    Configure:
    - Round-up transactions
    - Percentage-based saving from income
    - Fixed amount regular saving
    - Balance limits and safety nets
    """
    try:
        updated_settings = await savings_service.update_auto_save_settings(
            user_id=current_user["user_id"],
            settings_data=settings_data
        )
        
        return BaseResponse(
            success=True,
            message="Auto-save settings updated successfully",
            data=updated_settings
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update auto-save settings: {str(e)}"
        )

@router.get(
    "/health",
    response_model=BaseResponse,
    summary="Savings Service Health Check",
    description="Check savings service health and status"
)
async def savings_health_check():
    """
    Health check endpoint for savings service.
    
    Returns service status and basic metrics.
    """
    try:
        health_status = await savings_service.health_check()
        
        return BaseResponse(
            success=True,
            message="Savings service is healthy",
            data=health_status
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Savings service health check failed: {str(e)}"
        )

# Fixed Deposit Endpoints
@router.get(
    "/fixed-deposits",
    response_model=BaseResponse,
    summary="Get Fixed Deposits",
    description="Retrieve user's fixed deposits"
)
async def get_fixed_deposits(
    current_user: dict = Depends(get_current_user)
):
    """
    Get user's fixed deposits.
    
    Returns all active and matured fixed deposits for the user.
    """
    try:
        fixed_deposits = await savings_service.get_user_fixed_deposits(
            user_id=current_user["user_id"]
        )
        
        return BaseResponse(
            success=True,
            message="Fixed deposits retrieved successfully",
            data=fixed_deposits
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve fixed deposits: {str(e)}"
        )

@router.post(
    "/fixed-deposits",
    response_model=BaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Fixed Deposit",
    description="Create a new fixed deposit"
)
async def create_fixed_deposit(
    fd_data: FixedDepositCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new fixed deposit.
    
    Locks in savings for a specified term with guaranteed returns.
    """
    try:
        fixed_deposit = await savings_service.create_fixed_deposit(
            user_id=current_user["user_id"],
            fd_data=fd_data
        )
        
        return BaseResponse(
            success=True,
            message="Fixed deposit created successfully",
            data=fixed_deposit
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create fixed deposit: {str(e)}"
        )

# Automated Savings Endpoints
@router.get(
    "/automated-savings",
    response_model=BaseResponse,
    summary="Get Automated Savings",
    description="Retrieve user's automated savings"
)
async def get_automated_savings(
    current_user: dict = Depends(get_current_user)
):
    """
    Get user's automated savings plans.
    
    Returns all active automated savings configurations.
    """
    try:
        automated_savings = await savings_service.get_user_automated_savings(
            user_id=current_user["user_id"]
        )
        
        return BaseResponse(
            success=True,
            message="Automated savings retrieved successfully",
            data=automated_savings
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve automated savings: {str(e)}"
        )

@router.post(
    "/automated-savings",
    response_model=BaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Automated Saving",
    description="Create a new automated saving plan"
)
async def create_automated_saving(
    as_data: AutomatedSavingCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new automated saving plan.
    
    Sets up regular automatic transfers to savings.
    """
    try:
        automated_saving = await savings_service.create_automated_saving(
            user_id=current_user["user_id"],
            as_data=as_data
        )
        
        return BaseResponse(
            success=True,
            message="Automated saving created successfully",
            data=automated_saving
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create automated saving: {str(e)}"
        )

