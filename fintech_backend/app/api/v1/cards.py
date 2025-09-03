"""
Card management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Optional, List
import asyncio

from app.models.card import (
    Card, CardType, CardStatus, CardCreateRequest, CardUpdateRequest,
    CardStatusRequest, CardLimitRequest, CardPinChangeRequest,
    CardListResponse, CardResponse, CardCreatedResponse, 
    CardLimitsResponse, CardUsageResponse
)
from app.services.card_service import CardService, get_card_service
from app.core.exceptions import (
    ValidationError, NotFoundError, BusinessLogicError,
    UnauthorizedError, InsufficientFundsError
)
from app.utils.response import success_response
from app.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/cards", tags=["Cards"])


@router.get("/", response_model=CardListResponse)
async def list_cards(
    user_id: str = Query(..., description="User ID to list cards for"),
    card_type: Optional[CardType] = Query(None, description="Filter by card type"),
    status: Optional[CardStatus] = Query(None, description="Filter by card status"),
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    card_service: CardService = Depends(get_card_service)
):
    """
    List all cards for a user with optional filtering.
    
    Returns a list of payment cards belonging to the user,
    with optional filtering by type, status, or account.
    """
    try:
        logger.info(f"API: Listing cards for user {user_id}")
        
        cards = await card_service.list_user_cards(
            user_id=user_id,
            card_type=card_type,
            status=status,
            account_id=account_id
        )
        
        return success_response(
            data={
                "cards": cards,
                "total_count": len(cards)
            },
            message=f"Retrieved {len(cards)} cards successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing cards: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(
    card_id: str = Path(..., description="Card ID"),
    user_id: str = Query(..., description="User ID"),
    card_service: CardService = Depends(get_card_service)
):
    """
    Get detailed information for a specific card.
    
    Returns comprehensive card details including limits,
    settings, and current status.
    """
    try:
        logger.info(f"API: Getting card details for {card_id}")
        
        card = await card_service.get_card_details(card_id, user_id)
        
        return success_response(
            data={"card": card},
            message="Card details retrieved successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting card: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/", response_model=CardCreatedResponse)
async def create_card(
    user_id: str = Query(..., description="User ID"),
    request: CardCreateRequest = ...,
    card_service: CardService = Depends(get_card_service)
):
    """
    Create a new payment card.
    
    Creates a new card for the specified user and account
    with the requested settings and default spending limits.
    """
    try:
        logger.info(f"API: Creating card for user {user_id}")
        
        result = await card_service.create_card(user_id, request)
        
        return success_response(
            data={
                "card": result["card"],
                "delivery_estimate": result["delivery_estimate"]
            },
            message="Card created successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating card: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{card_id}", response_model=CardResponse)
async def update_card(
    card_id: str = Path(..., description="Card ID"),
    user_id: str = Query(..., description="User ID"),
    request: CardUpdateRequest = ...,
    card_service: CardService = Depends(get_card_service)
):
    """
    Update card settings and preferences.
    
    Updates card settings such as name, contactless settings,
    online payments, and international transactions.
    """
    try:
        logger.info(f"API: Updating card {card_id}")
        
        card = await card_service.update_card_settings(card_id, user_id, request)
        
        return success_response(
            data={"card": card},
            message="Card updated successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating card: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{card_id}/status", response_model=CardResponse)
async def change_card_status(
    card_id: str = Path(..., description="Card ID"),
    user_id: str = Query(..., description="User ID"),
    request: CardStatusRequest = ...,
    card_service: CardService = Depends(get_card_service)
):
    """
    Change card status (freeze, unfreeze, block, cancel).
    
    Updates the card status to control transaction authorization.
    Valid transitions depend on current status.
    """
    try:
        logger.info(f"API: Changing status for card {card_id} to {request.status}")
        
        card = await card_service.change_card_status(card_id, user_id, request)
        
        return success_response(
            data={"card": card},
            message=f"Card status changed to {request.status} successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error changing card status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")




@router.get("/{card_id}/limits", response_model=CardLimitsResponse)
async def get_card_limits(
    card_id: str = Path(..., description="Card ID"),
    user_id: str = Query(..., description="User ID"),
    card_service: CardService = Depends(get_card_service)
):
    """
    Get card spending limits and current usage.
    
    Returns all configured spending limits with current usage
    and remaining amounts for each limit type.
    """
    try:
        logger.info(f"API: Getting limits for card {card_id}")
        
        result = await card_service.get_card_limits(card_id, user_id)
        
        return success_response(
            data={
                "limits": result["limits"],
                "remaining_limits": result["remaining_limits"]
            },
            message="Card limits retrieved successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting card limits: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{card_id}/limits", response_model=CardLimitsResponse)
async def set_card_limit(
    card_id: str = Path(..., description="Card ID"),
    user_id: str = Query(..., description="User ID"),
    request: CardLimitRequest = ...,
    card_service: CardService = Depends(get_card_service)
):
    """
    Set or update a card spending limit.
    
    Creates or updates a spending limit for specific transaction
    types and time periods.
    """
    try:
        logger.info(f"API: Setting limit for card {card_id}")
        
        limits = await card_service.set_card_limit(card_id, user_id, request)
        
        # Calculate remaining limits
        remaining_limits = {}
        for limit in limits:
            if limit.is_enabled:
                key = f"{limit.transaction_type}_{limit.period}"
                remaining = max(limit.limit_amount - limit.current_usage, 0)
                remaining_limits[key] = remaining
        
        return success_response(
            data={
                "limits": limits,
                "remaining_limits": remaining_limits
            },
            message="Card limit set successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error setting card limit: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{card_id}/pin", response_model=dict)
async def change_pin(
    card_id: str = Path(..., description="Card ID"),
    user_id: str = Query(..., description="User ID"),
    request: CardPinChangeRequest = ...,
    card_service: CardService = Depends(get_card_service)
):
    """
    Change card PIN.
    
    Updates the card PIN after validating the current PIN.
    Requires current PIN for security.
    """
    try:
        logger.info(f"API: Changing PIN for card {card_id}")
        
        success = await card_service.change_pin(card_id, user_id, request)
        
        return success_response(
            data={"success": success},
            message="PIN changed successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized or incorrect PIN: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error changing PIN: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{card_id}/usage", response_model=CardUsageResponse)
async def get_card_usage(
    card_id: str = Path(..., description="Card ID"),
    user_id: str = Query(..., description="User ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    card_service: CardService = Depends(get_card_service)
):
    """
    Get card usage analytics and spending patterns.
    
    Returns detailed analytics including transaction summaries,
    spending by category, and usage patterns over the specified period.
    """
    try:
        logger.info(f"API: Getting usage analytics for card {card_id}")
        
        analytics = await card_service.get_card_usage_analytics(card_id, user_id, days)
        
        return success_response(
            data=analytics,
            message="Card usage analytics retrieved successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting card usage: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Convenience endpoints for common operations
@router.post("/{card_id}/freeze", response_model=CardResponse)
async def freeze_card_endpoint(
    card_id: str = Path(..., description="Card ID"),
    user_id: str = Query(..., description="User ID"),
    reason: Optional[str] = Query("User requested", description="Reason for freezing"),
    card_service: CardService = Depends(get_card_service)
):
    """
    Freeze a card to prevent all transactions.
    
    Convenience endpoint for freezing a card.
    Equivalent to changing status to 'frozen'.
    """
    try:
        logger.info(f"API: Freezing card {card_id}")
        
        card = await card_service.freeze_card(card_id, user_id, reason)
        
        return success_response(
            data={"card": card},
            message="Card frozen successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error freezing card: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{card_id}/unfreeze", response_model=CardResponse)
async def unfreeze_card_endpoint(
    card_id: str = Path(..., description="Card ID"),
    user_id: str = Query(..., description="User ID"),
    reason: Optional[str] = Query("User requested", description="Reason for unfreezing"),
    card_service: CardService = Depends(get_card_service)
):
    """
    Unfreeze a card to allow transactions.
    
    Convenience endpoint for unfreezing a card.
    Equivalent to changing status to 'active'.
    """
    try:
        logger.info(f"API: Unfreezing card {card_id}")
        
        card = await card_service.unfreeze_card(card_id, user_id, reason)
        
        return success_response(
            data={"card": card},
            message="Card unfrozen successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error unfreezing card: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{card_id}/block", response_model=CardResponse)
async def block_card_endpoint(
    card_id: str = Path(..., description="Card ID"),
    user_id: str = Query(..., description="User ID"),
    reason: Optional[str] = Query("Security concern", description="Reason for blocking"),
    card_service: CardService = Depends(get_card_service)
):
    """
    Block a card due to security concerns.
    
    Convenience endpoint for blocking a card.
    Equivalent to changing status to 'blocked'.
    """
    try:
        logger.info(f"API: Blocking card {card_id}")
        
        card = await card_service.block_card(card_id, user_id, reason)
        
        return success_response(
            data={"card": card},
            message="Card blocked successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error blocking card: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def cards_health():
    """
    Health check endpoint for card service.
    
    Returns the operational status of the card management service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time
        
        return success_response(
            data={
                "service": "card_service",
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00Z",
                "version": "1.0.0"
            },
            message="Card service is healthy"
        )
        
    except Exception as e:
        logger.error(f"Card service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
