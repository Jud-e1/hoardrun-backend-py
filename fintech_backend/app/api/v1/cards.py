"""
Card management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from sqlalchemy.orm import Session
from typing import Optional, List
import asyncio

from app.models.flat_card import (
    Card, CardType, CardStatus, CardCreateRequest, CardUpdateRequest,
    CardActivationRequest, CardPinChangeRequest, CardLimitRequest,
    CardListResponse, CardResponse, CardCreatedResponse, 
    CardActivationResponse, CardTransactionResponse
)
from app.services.database_card_service import DatabaseCardService
from app.database.config import get_db
from app.core.exceptions import (
    ValidationException, CardNotFoundException, BusinessRuleViolationException,
    FintechException, InsufficientFundsException
)
from app.utils.response import success_response
from app.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/cards", tags=["Cards"])


def get_card_service():
    """Dependency to get card service instance"""
    return DatabaseCardService()


@router.get("/", response_model=CardListResponse)
async def list_cards(
    user_id: str = Query(..., description="User ID to list cards for"),
    card_type: Optional[CardType] = Query(None, description="Filter by card type"),
    status: Optional[CardStatus] = Query(None, description="Filter by card status"),
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    db: Session = Depends(get_db),
    card_service: DatabaseCardService = Depends(get_card_service)
):
    """
    List all cards for a user with optional filtering.
    
    Returns a list of payment cards belonging to the user,
    with optional filtering by type, status, or account.
    """
    try:
        logger.info(f"API: Listing cards for user {user_id}")
        
        cards = card_service.get_user_cards(user_id, db)
        
        # Apply filters if provided
        if card_type:
            cards = [card for card in cards if card.card_type == card_type.value]
        if status:
            cards = [card for card in cards if card.status == status.value]
        if account_id:
            cards = [card for card in cards if card.account_id == account_id]
        
        return success_response(
            data={
                "cards": cards,
                "total_count": len(cards)
            },
            message=f"Retrieved {len(cards)} cards successfully"
        )
        
    except CardNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing cards: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(
    card_id: str = Path(..., description="Card ID"),
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db),
    card_service: DatabaseCardService = Depends(get_card_service)
):
    """
    Get detailed information for a specific card.
    
    Returns comprehensive card details including limits,
    settings, and current status.
    """
    try:
        logger.info(f"API: Getting card details for {card_id}")
        
        card = card_service.get_card_by_id(card_id, user_id, db)
        
        return success_response(
            data={"card": card},
            message="Card details retrieved successfully"
        )
        
    except CardNotFoundException as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting card: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/", response_model=CardCreatedResponse)
async def create_card(
    user_id: str = Query(..., description="User ID"),
    request: CardCreateRequest = ...,
    db: Session = Depends(get_db),
    card_service: DatabaseCardService = Depends(get_card_service)
):
    """
    Create a new payment card.
    
    Creates a new card for the specified user and account
    with the requested settings and default spending limits.
    """
    try:
        logger.info(f"API: Creating card for user {user_id}")
        
        card = card_service.create_card(user_id, request, db)
        
        # Estimate delivery time (mock data)
        delivery_estimate = "5-7 business days"
        
        return success_response(
            data={
                "card": card,
                "delivery_estimate": delivery_estimate
            },
            message="Card created successfully"
        )
        
    except CardNotFoundException as e:
        logger.error(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationException as e:
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
    db: Session = Depends(get_db),
    card_service: DatabaseCardService = Depends(get_card_service)
):
    """
    Update card settings and preferences.
    
    Updates card settings such as name, contactless settings,
    online payments, and international transactions.
    """
    try:
        logger.info(f"API: Updating card {card_id}")
        
        card = card_service.update_card(card_id, user_id, request, db)
        
        return success_response(
            data={"card": card},
            message="Card updated successfully"
        )
        
    except CardNotFoundException as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating card: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Convenience endpoints for common operations
@router.post("/{card_id}/freeze", response_model=CardResponse)
async def freeze_card_endpoint(
    card_id: str = Path(..., description="Card ID"),
    user_id: str = Query(..., description="User ID"),
    reason: Optional[str] = Query("User requested", description="Reason for freezing"),
    db: Session = Depends(get_db),
    card_service: DatabaseCardService = Depends(get_card_service)
):
    """
    Freeze a card to prevent all transactions.
    
    Convenience endpoint for freezing a card.
    Equivalent to changing status to 'frozen'.
    """
    try:
        logger.info(f"API: Freezing card {card_id}")
        
        card = card_service.block_card(card_id, user_id, db)
        
        return success_response(
            data={"card": card},
            message="Card frozen successfully"
        )
        
    except CardNotFoundException as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleViolationException as e:
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
    db: Session = Depends(get_db),
    card_service: DatabaseCardService = Depends(get_card_service)
):
    """
    Unfreeze a card to allow transactions.
    
    Convenience endpoint for unfreezing a card.
    Equivalent to changing status to 'active'.
    """
    try:
        logger.info(f"API: Unfreezing card {card_id}")
        
        card = card_service.unblock_card(card_id, user_id, db)
        
        return success_response(
            data={"card": card},
            message="Card unfrozen successfully"
        )
        
    except CardNotFoundException as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleViolationException as e:
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
    db: Session = Depends(get_db),
    card_service: DatabaseCardService = Depends(get_card_service)
):
    """
    Block a card due to security concerns.
    
    Convenience endpoint for blocking a card.
    Equivalent to changing status to 'blocked'.
    """
    try:
        logger.info(f"API: Blocking card {card_id}")
        
        card = card_service.block_card(card_id, user_id, db)
        
        return success_response(
            data={"card": card},
            message="Card blocked successfully"
        )
        
    except CardNotFoundException as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error blocking card: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{card_id}", response_model=dict)
async def delete_card(
    card_id: str = Path(..., description="Card ID"),
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db),
    card_service: DatabaseCardService = Depends(get_card_service)
):
    """
    Delete a card permanently.
    
    Permanently removes the card from the system.
    This action cannot be undone.
    """
    try:
        logger.info(f"API: Deleting card {card_id}")
        
        success = card_service.delete_card(card_id, user_id, db)
        
        return success_response(
            data={"success": success},
            message="Card deleted successfully"
        )
        
    except CardNotFoundException as e:
        logger.error(f"Card not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting card: {e}")
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
