"""
Money transfer API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from sqlalchemy.orm import Session
from typing import Optional, List
import asyncio

from ...models.transfer import (
    TransferType, TransferStatus, TransferCreateRequest,
    TransferResponse, TransferListResponse
)
from ...services.database_transfer_service import DatabaseTransferService
from ...database.config import get_db
from ...core.exceptions import (
    ValidationException, AccountNotFoundException, BusinessRuleViolationException
)
from ...utils.response import success_response
from ...config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/transfers", tags=["Money Transfers"])


def get_transfer_service():
    """Dependency to get transfer service instance"""
    return DatabaseTransferService()


@router.get("/", response_model=TransferListResponse)
async def list_transfers(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
    transfer_service: DatabaseTransferService = Depends(get_transfer_service)
):
    """
    List user's money transfers.
    
    Returns a paginated list of transfers with optional
    status filtering and pending transfer counts.
    """
    try:
        logger.info(f"API: Listing transfers for user {user_id}")
        
        transfers = transfer_service.get_user_transfers(user_id, limit, offset, db)
        
        result = {
            "transfers": transfers,
            "total_count": len(transfers),
            "has_more": len(transfers) == limit
        }
        
        return success_response(
            data=result,
            message=f"Retrieved {len(transfers)} transfers"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing transfers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{transfer_id}", response_model=TransferResponse)
async def get_transfer(
    transfer_id: str = Path(..., description="Transfer ID"),
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db),
    transfer_service: DatabaseTransferService = Depends(get_transfer_service)
):
    """
    Get transfer details.
    
    Returns detailed transfer information including
    status, amounts, and transaction history.
    """
    try:
        logger.info(f"API: Getting transfer {transfer_id}")
        
        transfer = transfer_service.get_transfer_by_id(transfer_id, user_id, db)
        
        return success_response(
            data={"transfer": transfer},
            message="Transfer details retrieved successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Transfer not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transfer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/", response_model=TransferResponse)
async def create_transfer(
    user_id: str = Query(..., description="User ID"),
    request: TransferCreateRequest = ...,
    db: Session = Depends(get_db),
    transfer_service: DatabaseTransferService = Depends(get_transfer_service)
):
    """
    Create a new money transfer.
    
    Executes a transfer between accounts with
    automatic balance updates and transaction logging.
    """
    try:
        logger.info(f"API: Creating transfer for user {user_id}")
        
        transfer = transfer_service.create_transfer(user_id, request, db)
        
        return success_response(
            data={"transfer": transfer},
            message="Transfer created successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating transfer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/account/{account_id}", response_model=TransferListResponse)
async def get_account_transfers(
    account_id: str = Path(..., description="Account ID"),
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
    transfer_service: DatabaseTransferService = Depends(get_transfer_service)
):
    """
    Get transfers for a specific account.
    
    Returns all transfers involving the specified account
    (both sent and received) with pagination.
    """
    try:
        logger.info(f"API: Getting transfers for account {account_id}")
        
        transfers = transfer_service.get_account_transfers(account_id, user_id, limit, offset, db)
        
        result = {
            "transfers": transfers,
            "total_count": len(transfers),
            "has_more": len(transfers) == limit
        }
        
        return success_response(
            data=result,
            message=f"Retrieved {len(transfers)} transfers for account"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting account transfers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sent", response_model=TransferListResponse)
async def get_sent_transfers(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
    transfer_service: DatabaseTransferService = Depends(get_transfer_service)
):
    """
    Get transfers sent by the user.
    
    Returns all outgoing transfers initiated by the user.
    """
    try:
        logger.info(f"API: Getting sent transfers for user {user_id}")
        
        transfers = transfer_service.get_sent_transfers(user_id, limit, offset, db)
        
        result = {
            "transfers": transfers,
            "total_count": len(transfers),
            "has_more": len(transfers) == limit
        }
        
        return success_response(
            data=result,
            message=f"Retrieved {len(transfers)} sent transfers"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting sent transfers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/received", response_model=TransferListResponse)
async def get_received_transfers(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
    transfer_service: DatabaseTransferService = Depends(get_transfer_service)
):
    """
    Get transfers received by the user.
    
    Returns all incoming transfers received by the user.
    """
    try:
        logger.info(f"API: Getting received transfers for user {user_id}")
        
        transfers = transfer_service.get_received_transfers(user_id, limit, offset, db)
        
        result = {
            "transfers": transfers,
            "total_count": len(transfers),
            "has_more": len(transfers) == limit
        }
        
        return success_response(
            data=result,
            message=f"Retrieved {len(transfers)} received transfers"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting received transfers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{transfer_id}/cancel", response_model=TransferResponse)
async def cancel_transfer(
    transfer_id: str = Path(..., description="Transfer ID"),
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db),
    transfer_service: DatabaseTransferService = Depends(get_transfer_service)
):
    """
    Cancel a pending transfer.
    
    Cancels a transfer that has not yet been completed.
    Only pending transfers can be cancelled.
    """
    try:
        logger.info(f"API: Cancelling transfer {transfer_id}")
        
        transfer = transfer_service.cancel_transfer(transfer_id, user_id, db)
        
        return success_response(
            data={"transfer": transfer},
            message="Transfer cancelled successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Transfer not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error cancelling transfer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/summary", response_model=dict)
async def get_transfer_summary(
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db),
    transfer_service: DatabaseTransferService = Depends(get_transfer_service)
):
    """
    Get transfer summary statistics.
    
    Returns comprehensive summary including sent/received amounts,
    counts, and status breakdowns.
    """
    try:
        logger.info(f"API: Getting transfer summary for user {user_id}")
        
        summary = transfer_service.get_transfer_summary(user_id, db)
        
        return success_response(
            data=summary,
            message="Transfer summary retrieved successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transfer summary: {e}")
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
