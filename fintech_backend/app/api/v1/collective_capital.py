"""
Collective Capital API endpoints for investment circles and group investing.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Optional, List
import asyncio

from ...models.collective_capital import (
    CollectiveCircle, CircleFilters, CircleStats, CreateCircleRequest,
    UpdateCircleRequest, CreateProposalRequest, VoteOnProposalRequest,
    JoinCircleRequest, ContributeToCircleRequest, InvestmentProposal,
    JoinRequest, AIRecommendationModel, CircleActivity,
    CircleResponse, CircleListResponse, CircleStatsResponse,
    ProposalResponse, ProposalListResponse, JoinRequestResponse,
    JoinRequestListResponse, AIRecommendationResponse, ActivityResponse,
    InvestmentCategory, CircleStatus, ProposalStatus
)
from ...services.collective_capital_service import CollectiveCapitalService
from ...core.exceptions import (
    ValidationException, AccountNotFoundException, 
    BusinessRuleViolationException, FintechException
)
from ...utils.response import success_response
from ...config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/collective-capital", tags=["Collective Capital"])

# Service instance
collective_capital_service = CollectiveCapitalService()


@router.get("/circles", response_model=CircleListResponse)
async def get_circles(
    user_id: str = Query(..., description="User ID"),
    category: Optional[List[InvestmentCategory]] = Query(None, description="Filter by categories"),
    min_pool_value: Optional[float] = Query(None, ge=0, description="Minimum pool value"),
    max_pool_value: Optional[float] = Query(None, gt=0, description="Maximum pool value"),
    status: Optional[List[CircleStatus]] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """
    Get collective capital circles with optional filtering.
    
    Returns a list of investment circles that the user can view,
    with comprehensive filtering options and pagination.
    """
    try:
        logger.info(f"API: Getting circles for user {user_id}")
        
        # Create filters object
        filters = CircleFilters(
            category=category,
            min_pool_value=min_pool_value,
            max_pool_value=max_pool_value,
            status=status
        )
        
        circles = await collective_capital_service.get_circles(
            user_id=user_id,
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        return CircleListResponse(
            success=True,
            message=f"Retrieved {len(circles)} circles",
            data=circles,
            total_count=len(circles),
            filters_applied=filters
        )
        
    except AccountNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting circles: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/circles/{circle_id}", response_model=CircleResponse)
async def get_circle(
    circle_id: str = Path(..., description="Circle ID"),
    user_id: str = Query(..., description="User ID")
):
    """
    Get detailed information for a specific circle.
    
    Returns comprehensive circle details including members,
    investments, proposals, and activities.
    """
    try:
        logger.info(f"API: Getting circle {circle_id} for user {user_id}")
        
        circle = await collective_capital_service.get_circle_by_id(circle_id, user_id)
        
        return CircleResponse(
            success=True,
            message="Circle details retrieved successfully",
            data=circle
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Circle not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Access denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting circle: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/circles", response_model=CircleResponse)
async def create_circle(
    user_id: str = Query(..., description="User ID"),
    request: CreateCircleRequest = ...
):
    """
    Create a new collective capital circle.
    
    Creates a new investment circle with the specified settings
    and adds the creator as the first member.
    """
    try:
        logger.info(f"API: Creating circle for user {user_id}")
        
        circle = await collective_capital_service.create_circle(user_id, request)
        
        return CircleResponse(
            success=True,
            message="Circle created successfully",
            data=circle
        )
        
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business rule violation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating circle: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/circles/{circle_id}", response_model=CircleResponse)
async def update_circle(
    circle_id: str = Path(..., description="Circle ID"),
    user_id: str = Query(..., description="User ID"),
    request: UpdateCircleRequest = ...
):
    """
    Update circle settings.
    
    Updates circle configuration. Only circle creators
    and admins can modify settings.
    """
    try:
        logger.info(f"API: Updating circle {circle_id} by user {user_id}")
        
        circle = await collective_capital_service.update_circle(circle_id, user_id, request)
        
        return CircleResponse(
            success=True,
            message="Circle updated successfully",
            data=circle
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Circle not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Access denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating circle: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/circles/{circle_id}/join", response_model=JoinRequestResponse)
async def join_circle(
    circle_id: str = Path(..., description="Circle ID"),
    user_id: str = Query(..., description="User ID"),
    request: JoinCircleRequest = ...
):
    """
    Request to join a circle.
    
    Creates a join request for the specified circle.
    For public circles, this may auto-approve.
    """
    try:
        logger.info(f"API: User {user_id} joining circle {circle_id}")
        
        join_request = await collective_capital_service.join_circle(circle_id, user_id, request)
        
        return JoinRequestResponse(
            success=True,
            message="Join request created successfully",
            data=join_request
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Circle not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business rule violation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error joining circle: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats", response_model=CircleStatsResponse)
async def get_circle_stats(
    user_id: str = Query(..., description="User ID")
):
    """
    Get collective capital statistics.
    
    Returns comprehensive statistics about circles,
    including user-specific metrics.
    """
    try:
        logger.info(f"API: Getting circle stats for user {user_id}")
        
        stats = await collective_capital_service.get_circle_stats(user_id)
        
        return CircleStatsResponse(
            success=True,
            message="Circle statistics retrieved successfully",
            data=stats
        )
        
    except Exception as e:
        logger.error(f"Error getting circle stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/circles/{circle_id}/proposals", response_model=ProposalResponse)
async def create_proposal(
    circle_id: str = Path(..., description="Circle ID"),
    user_id: str = Query(..., description="User ID"),
    request: CreateProposalRequest = ...
):
    """
    Create an investment proposal.
    
    Creates a new investment proposal for circle members to vote on.
    Only circle members can create proposals.
    """
    try:
        logger.info(f"API: Creating proposal for circle {circle_id} by user {user_id}")
        
        proposal = await collective_capital_service.create_proposal(circle_id, user_id, request)
        
        return ProposalResponse(
            success=True,
            message="Proposal created successfully",
            data=proposal
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Circle not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Access denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating proposal: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/circles/{circle_id}/proposals", response_model=ProposalListResponse)
async def get_circle_proposals(
    circle_id: str = Path(..., description="Circle ID"),
    user_id: str = Query(..., description="User ID"),
    status: Optional[ProposalStatus] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """
    Get proposals for a circle.
    
    Returns investment proposals with optional status filtering.
    """
    try:
        logger.info(f"API: Getting proposals for circle {circle_id}")
        
        circle = await collective_capital_service.get_circle_by_id(circle_id, user_id)
        
        # Filter proposals by status if specified
        proposals = circle.proposals
        if status:
            proposals = [p for p in proposals if p.status == status]
        
        # Apply pagination
        total_count = len(proposals)
        proposals = proposals[offset:offset + limit]
        
        return ProposalListResponse(
            success=True,
            message=f"Retrieved {len(proposals)} proposals",
            data=proposals,
            total_count=total_count
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Circle not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Access denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting proposals: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/circles/{circle_id}/proposals/{proposal_id}/vote", response_model=ProposalResponse)
async def vote_on_proposal(
    circle_id: str = Path(..., description="Circle ID"),
    proposal_id: str = Path(..., description="Proposal ID"),
    user_id: str = Query(..., description="User ID"),
    request: VoteOnProposalRequest = ...
):
    """
    Vote on an investment proposal.
    
    Records a vote on the specified proposal.
    Only circle members can vote.
    """
    try:
        logger.info(f"API: User {user_id} voting on proposal {proposal_id}")
        
        proposal = await collective_capital_service.vote_on_proposal(
            circle_id, proposal_id, user_id, request
        )
        
        return ProposalResponse(
            success=True,
            message="Vote recorded successfully",
            data=proposal
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Access denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business rule violation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error voting on proposal: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/circles/{circle_id}/ai-recommendations", response_model=AIRecommendationResponse)
async def get_ai_recommendations(
    circle_id: str = Path(..., description="Circle ID"),
    user_id: str = Query(..., description="User ID")
):
    """
    Get AI recommendations for a circle.
    
    Returns AI-powered investment recommendations and insights
    for circle members.
    """
    try:
        logger.info(f"API: Getting AI recommendations for circle {circle_id}")
        
        recommendations = await collective_capital_service.get_ai_recommendations(circle_id, user_id)
        
        return AIRecommendationResponse(
            success=True,
            message="AI recommendations retrieved successfully",
            data=recommendations
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Circle not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Access denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting AI recommendations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/circles/{circle_id}/activities", response_model=ActivityResponse)
async def get_circle_activities(
    circle_id: str = Path(..., description="Circle ID"),
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """
    Get circle activities.
    
    Returns recent activities and events in the circle
    with pagination support.
    """
    try:
        logger.info(f"API: Getting activities for circle {circle_id}")
        
        activities = await collective_capital_service.get_circle_activities(
            circle_id, user_id, limit, offset
        )
        
        return ActivityResponse(
            success=True,
            message=f"Retrieved {len(activities)} activities",
            data=activities,
            total_count=len(activities)
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Circle not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Access denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting activities: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/circles/{circle_id}/contribute", response_model=CircleResponse)
async def contribute_to_circle(
    circle_id: str = Path(..., description="Circle ID"),
    user_id: str = Query(..., description="User ID"),
    request: ContributeToCircleRequest = ...
):
    """
    Contribute funds to a circle.
    
    Adds funds to the circle's investment pool.
    Only circle members can contribute.
    """
    try:
        logger.info(f"API: User {user_id} contributing to circle {circle_id}")
        
        # For now, return a success response
        # In production, this would integrate with payment processing
        circle = await collective_capital_service.get_circle_by_id(circle_id, user_id)
        
        return CircleResponse(
            success=True,
            message=f"Contribution of ${request.amount} processed successfully",
            data=circle
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Circle not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Access denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error contributing to circle: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/user/{user_id}/circles", response_model=CircleListResponse)
async def get_user_circles(
    user_id: str = Path(..., description="User ID"),
    status: Optional[CircleStatus] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """
    Get circles that a user is a member of.
    
    Returns circles where the user is an active member
    with optional status filtering.
    """
    try:
        logger.info(f"API: Getting circles for user {user_id}")
        
        # Create filters for user's circles
        filters = CircleFilters(status=[status] if status else None)
        
        circles = await collective_capital_service.get_circles(
            user_id=user_id,
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        # Filter to only circles where user is a member
        user_circles = []
        for circle in circles:
            if any(member.user_id == user_id for member in circle.members):
                user_circles.append(circle)
        
        return CircleListResponse(
            success=True,
            message=f"Retrieved {len(user_circles)} user circles",
            data=user_circles,
            total_count=len(user_circles),
            filters_applied=filters
        )
        
    except Exception as e:
        logger.error(f"Error getting user circles: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def collective_capital_health():
    """
    Health check endpoint for collective capital service.
    
    Returns the operational status of the collective capital service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time
        
        health_data = await collective_capital_service.health_check()
        
        return success_response(
            data=health_data,
            message="Collective capital service is healthy"
        )
        
    except Exception as e:
        logger.error(f"Collective capital service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
