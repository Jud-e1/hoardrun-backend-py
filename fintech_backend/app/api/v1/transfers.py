"""
Money transfer API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Optional, List
import asyncio

from app.models.transfer import (
    TransferType, TransferStatus, BeneficiaryCreateRequest, BeneficiaryUpdateRequest,
    TransferQuoteRequest, TransferInitiateRequest, TransferCancelRequest,
    BeneficiaryListResponse, BeneficiaryResponse, TransferQuoteResponse,
    TransferResponse, TransferListResponse, TransferTrackingResponse,
    ExchangeRateResponse, TransferLimitsResponse, TransferFeesResponse,
    TransferCorridorsResponse
)
from app.services.transfer_service import MoneyTransferService, get_money_transfer_service
from app.core.exceptions import (
    ValidationError, NotFoundError, BusinessLogicError, UnauthorizedError
)
from app.utils.response import success_response
from app.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/transfers", tags=["Money Transfers"])


# Beneficiary endpoints
@router.get("/beneficiaries", response_model=BeneficiaryListResponse)
async def list_beneficiaries(
    user_id: str = Query(..., description="User ID"),
    transfer_service: MoneyTransferService = Depends(get_money_transfer_service)
):
    """
    List all beneficiaries for a user.
    
    Returns all registered beneficiaries including favorites
    for quick access during transfer operations.
    """
    try:
        logger.info(f"API: Listing beneficiaries for user {user_id}")
        
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


@router.post("/beneficiaries", response_model=BeneficiaryResponse)
async def create_beneficiary(
    user_id: str = Query(..., description="User ID"),
    request: BeneficiaryCreateRequest = ...,
    transfer_service: MoneyTransferService = Depends(get_money_transfer_service)
):
    """
    Create a new beneficiary for money transfers.
    
    Registers a new beneficiary with banking details and
    initiates verification process.
    """
    try:
        logger.info(f"API: Creating beneficiary for user {user_id}")
        
        beneficiary = await transfer_service.create_beneficiary(user_id, request)
        
        return success_response(
            data={"beneficiary": beneficiary},
            message="Beneficiary created and verified successfully"
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


@router.patch("/beneficiaries/{beneficiary_id}", response_model=BeneficiaryResponse)
async def update_beneficiary(
    beneficiary_id: str = Path(..., description="Beneficiary ID"),
    user_id: str = Query(..., description="User ID"),
    request: BeneficiaryUpdateRequest = ...,
    transfer_service: MoneyTransferService = Depends(get_money_transfer_service)
):
    """
    Update beneficiary information.
    
    Updates editable beneficiary fields such as contact
    information, nickname, and notes.
    """
    try:
        logger.info(f"API: Updating beneficiary {beneficiary_id}")
        
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


@router.delete("/beneficiaries/{beneficiary_id}")
async def delete_beneficiary(
    beneficiary_id: str = Path(..., description="Beneficiary ID"),
    user_id: str = Query(..., description="User ID"),
    transfer_service: MoneyTransferService = Depends(get_money_transfer_service)
):
    """
    Delete a beneficiary.
    
    Permanently removes a beneficiary from the user's list.
    Cannot be undone.
    """
    try:
        logger.info(f"API: Deleting beneficiary {beneficiary_id}")
        
        success = await transfer_service.delete_beneficiary(user_id, beneficiary_id)
        
        return success_response(
            data={"deleted": success},
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


# Quote and rate endpoints
@router.post("/quote", response_model=TransferQuoteResponse)
async def get_transfer_quote(
    user_id: str = Query(..., description="User ID"),
    request: TransferQuoteRequest = ...,
    transfer_service: MoneyTransferService = Depends(get_money_transfer_service)
):
    """
    Get transfer quote with fees and exchange rates.
    
    Returns detailed cost breakdown including exchange rates,
    fees, and alternative priority options.
    """
    try:
        logger.info(f"API: Getting transfer quote for user {user_id}")
        
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
        logger.error(f"Error generating quote: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/rates", response_model=ExchangeRateResponse)
async def get_exchange_rates(
    base_currency: str = Query(..., description="Base currency code"),
    symbols: Optional[List[str]] = Query(None, description="Target currency symbols"),
    transfer_service: MoneyTransferService = Depends(get_money_transfer_service)
):
    """
    Get current exchange rates.
    
    Returns current exchange rates for supported currency pairs
    with validity periods and margins.
    """
    try:
        logger.info(f"API: Getting exchange rates for {base_currency}")
        
        result = await transfer_service.get_exchange_rates(base_currency, symbols)
        
        return success_response(
            data=result,
            message="Exchange rates retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting exchange rates: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Transfer endpoints
@router.post("/", response_model=TransferResponse)
async def initiate_transfer(
    user_id: str = Query(..., description="User ID"),
    quote_id: str = Query(..., description="Quote ID"),
    request: TransferInitiateRequest = ...,
    transfer_service: MoneyTransferService = Depends(get_money_transfer_service)
):
    """
    Initiate a money transfer.
    
    Executes a transfer based on a previous quote with
    the specified purpose and recipient message.
    """
    try:
        logger.info(f"API: Initiating transfer for user {user_id}")
        
        transfer = await transfer_service.initiate_transfer(user_id, quote_id, request)
        
        return success_response(
            data={"transfer": transfer},
            message="Transfer initiated successfully"
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
        logger.error(f"Error initiating transfer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=TransferListResponse)
async def list_transfers(
    user_id: str = Query(..., description="User ID"),
    status: Optional[TransferStatus] = Query(None, description="Filter by transfer status"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    transfer_service: MoneyTransferService = Depends(get_money_transfer_service)
):
    """
    List user's money transfers.
    
    Returns a paginated list of transfers with optional
    status filtering and pending transfer counts.
    """
    try:
        logger.info(f"API: Listing transfers for user {user_id}")
        
        result = await transfer_service.list_transfers(user_id, status, limit, offset)
        
        return success_response(
            data=result,
            message=f"Retrieved {len(result['transfers'])} transfers"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing transfers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{transfer_id}", response_model=TransferTrackingResponse)
async def track_transfer(
    transfer_id: str = Path(..., description="Transfer ID"),
    user_id: str = Query(..., description="User ID"),
    transfer_service: MoneyTransferService = Depends(get_money_transfer_service)
):
    """
    Track transfer status and progress.
    
    Returns detailed transfer tracking information including
    status history, estimated completion, and next updates.
    """
    try:
        logger.info(f"API: Tracking transfer {transfer_id}")
        
        result = await transfer_service.track_transfer(user_id, transfer_id)
        
        return success_response(
            data=result,
            message="Transfer tracking retrieved successfully"
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


@router.post("/{transfer_id}/cancel", response_model=TransferResponse)
async def cancel_transfer(
    transfer_id: str = Path(..., description="Transfer ID"),
    user_id: str = Query(..., description="User ID"),
    request: TransferCancelRequest = ...,
    transfer_service: MoneyTransferService = Depends(get_money_transfer_service)
):
    """
    Cancel a pending transfer.
    
    Cancels a transfer that has not yet been completed
    with optional fee refund.
    """
    try:
        logger.info(f"API: Cancelling transfer {transfer_id}")
        
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


# Information endpoints
@router.get("/limits", response_model=TransferLimitsResponse)
async def get_transfer_limits(
    user_id: str = Query(..., description="User ID"),
    transfer_service: MoneyTransferService = Depends(get_money_transfer_service)
):
    """
    Get user's transfer limits and usage.
    
    Returns daily, monthly, and annual transfer limits
    with current usage and remaining amounts.
    """
    try:
        logger.info(f"API: Getting transfer limits for user {user_id}")
        
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


@router.get("/fees", response_model=TransferFeesResponse)
async def get_fee_schedule(
    transfer_type: TransferType = Query(..., description="Transfer type"),
    transfer_service: MoneyTransferService = Depends(get_money_transfer_service)
):
    """
    Get fee schedule for transfer type.
    
    Returns detailed fee structure including base fees,
    variable rates, and priority upgrade costs.
    """
    try:
        logger.info(f"API: Getting fee schedule for {transfer_type}")
        
        result = await transfer_service.get_fee_schedule(transfer_type)
        
        return success_response(
            data=result,
            message="Fee schedule retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting fee schedule: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/corridors", response_model=TransferCorridorsResponse)
async def get_transfer_corridors(
    transfer_service: MoneyTransferService = Depends(get_money_transfer_service)
):
    """
    Get available transfer corridors.
    
    Returns supported country-to-country transfer routes
    with delivery times and compliance requirements.
    """
    try:
        logger.info("API: Getting transfer corridors")
        
        result = await transfer_service.get_transfer_corridors()
        
        return success_response(
            data=result,
            message="Transfer corridors retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting transfer corridors: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def transfers_health():
    """
    Health check endpoint for transfer service.
    
    Returns the operational status of the money transfer service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time
        
        return success_response(
            data={
                "service": "money_transfer_service",
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00Z",
                "version": "1.0.0"
            },
            message="Money transfer service is healthy"
        )
        
    except Exception as e:
        logger.error(f"Transfer service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
