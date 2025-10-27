"""
Money transfer API endpoints - Plaid-based implementation.
"""

from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional

from ..models.transfer import (
    BeneficiaryCreateRequest, BeneficiaryUpdateRequest,
    TransferQuoteRequest, TransferInitiateRequest, TransferCancelRequest,
    TransferStatus
)
from ..services.transfer_service import get_money_transfer_service
from ..core.exceptions import (
    ValidationError, NotFoundError, BusinessLogicError, UnauthorizedError
)
from ..utils.response import success_response
from ..config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/transfers", tags=["Money Transfers"])


# Beneficiary Management Endpoints

@router.get("/beneficiaries", response_model=dict)
async def list_beneficiaries(
    user_id: str = Query(..., description="User ID")
):
    """
    List all beneficiaries for a user.
    
    Returns all saved beneficiaries that can be used
    for Plaid transfers.
    """
    try:
        logger.info(f"API: Listing beneficiaries for user {user_id}")
        
        transfer_service = get_money_transfer_service()
        result = await transfer_service.list_beneficiaries(user_id)
        
        return success_response(
            data=result,
            message=f"Retrieved {result['total_count']} beneficiaries"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing beneficiaries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/beneficiaries", response_model=dict)
async def create_beneficiary(
    user_id: str = Query(..., description="User ID"),
    request: BeneficiaryCreateRequest = ...
):
    """
    Create a new beneficiary.
    
    Adds a new beneficiary that can receive Plaid transfers.
    """
    try:
        logger.info(f"API: Creating beneficiary for user {user_id}")
        
        transfer_service = get_money_transfer_service()
        beneficiary = await transfer_service.create_beneficiary(user_id, request)
        
        return success_response(
            data={"beneficiary": beneficiary},
            message="Beneficiary created successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating beneficiary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/beneficiaries/{beneficiary_id}", response_model=dict)
async def update_beneficiary(
    beneficiary_id: str = Path(..., description="Beneficiary ID"),
    user_id: str = Query(..., description="User ID"),
    request: BeneficiaryUpdateRequest = ...
):
    """
    Update beneficiary details.
    
    Updates information for an existing beneficiary.
    """
    try:
        logger.info(f"API: Updating beneficiary {beneficiary_id}")
        
        transfer_service = get_money_transfer_service()
        beneficiary = await transfer_service.update_beneficiary(user_id, beneficiary_id, request)
        
        return success_response(
            data={"beneficiary": beneficiary},
            message="Beneficiary updated successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Beneficiary not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating beneficiary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/beneficiaries/{beneficiary_id}", response_model=dict)
async def delete_beneficiary(
    beneficiary_id: str = Path(..., description="Beneficiary ID"),
    user_id: str = Query(..., description="User ID")
):
    """
    Delete a beneficiary.
    
    Removes a beneficiary from the user's saved list.
    """
    try:
        logger.info(f"API: Deleting beneficiary {beneficiary_id}")
        
        transfer_service = get_money_transfer_service()
        await transfer_service.delete_beneficiary(user_id, beneficiary_id)
        
        return success_response(
            data={"deleted": True},
            message="Beneficiary deleted successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Beneficiary not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting beneficiary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Transfer Endpoints

@router.post("/quote", response_model=dict)
async def get_transfer_quote(
    user_id: str = Query(..., description="User ID"),
    request: TransferQuoteRequest = ...
):
    """
    Get a transfer quote for Plaid transfers.
    
    Generates a quote with fees and exchange rates for
    transferring money from connected Plaid accounts.
    """
    try:
        logger.info(f"API: Getting Plaid transfer quote for user {user_id}")
        
        transfer_service = get_money_transfer_service()
        result = await transfer_service.get_transfer_quote(user_id, request)
        
        return success_response(
            data=result,
            message="Transfer quote generated successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transfer quote: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/initiate", response_model=dict)
async def initiate_transfer(
    user_id: str = Query(..., description="User ID"),
    quote_id: str = Query(..., description="Quote ID"),
    request: TransferInitiateRequest = ...
):
    """
    Initiate a Plaid transfer using a quote.
    
    Executes a money transfer from a connected Plaid account
    to a beneficiary using the provided quote.
    """
    try:
        logger.info(f"API: Initiating Plaid transfer for user {user_id}")
        
        transfer_service = get_money_transfer_service()
        transfer = await transfer_service.initiate_transfer(user_id, quote_id, request)
        
        return success_response(
            data={"transfer": transfer},
            message="Transfer initiated successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error initiating transfer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=dict)
async def list_transfers(
    user_id: str = Query(..., description="User ID"),
    status: Optional[TransferStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """
    List Plaid transfers for a user.
    
    Returns a paginated list of all Plaid transfers
    with optional status filtering.
    """
    try:
        logger.info(f"API: Listing Plaid transfers for user {user_id}")
        
        transfer_service = get_money_transfer_service()
        result = await transfer_service.list_transfers(user_id, status, limit, offset)
        
        return success_response(
            data=result,
            message=f"Retrieved {result['total_count']} transfers"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing transfers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{transfer_id}", response_model=dict)
async def track_transfer(
    transfer_id: str = Path(..., description="Transfer ID"),
    user_id: str = Query(..., description="User ID")
):
    """
    Track a Plaid transfer status.
    
    Returns current status and tracking information for a Plaid transfer
    including estimated completion time.
    """
    try:
        logger.info(f"API: Tracking Plaid transfer {transfer_id}")
        
        transfer_service = get_money_transfer_service()
        result = await transfer_service.track_transfer(user_id, transfer_id)
        
        return success_response(
            data=result,
            message="Transfer tracking information retrieved successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Transfer not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error tracking transfer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{transfer_id}/cancel", response_model=dict)
async def cancel_transfer(
    transfer_id: str = Path(..., description="Transfer ID"),
    user_id: str = Query(..., description="User ID"),
    request: TransferCancelRequest = ...
):
    """
    Cancel a Plaid transfer.
    
    Cancels a pending Plaid transfer if it's still cancellable.
    """
    try:
        logger.info(f"API: Cancelling Plaid transfer {transfer_id}")
        
        transfer_service = get_money_transfer_service()
        transfer = await transfer_service.cancel_transfer(user_id, transfer_id, request)
        
        return success_response(
            data={"transfer": transfer},
            message="Transfer cancelled successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Transfer not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error cancelling transfer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/limits", response_model=dict)
async def get_transfer_limits(
    user_id: str = Query(..., description="User ID")
):
    """
    Get transfer limits for Plaid transfers.
    
    Returns daily, monthly, and annual transfer limits
    along with current usage.
    """
    try:
        logger.info(f"API: Getting transfer limits for user {user_id}")
        
        transfer_service = get_money_transfer_service()
        result = await transfer_service.get_transfer_limits(user_id)
        
        return success_response(
            data=result,
            message="Transfer limits retrieved successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transfer limits: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def transfers_health():
    """
    Health check endpoint for Plaid transfer service.
    
    Returns the operational status of the Plaid money transfer service.
    """
    try:
        return success_response(
            data={
                "service": "plaid_transfer_service",
                "status": "healthy",
                "version": "2.0.0",
                "provider": "Plaid"
            },
            message="Plaid transfer service is healthy"
        )
        
    except Exception as e:
        logger.error(f"Transfer service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
