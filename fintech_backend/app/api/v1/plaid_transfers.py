"""
Plaid Transfer API endpoints.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from decimal import Decimal

from ..services.plaid_transfer_service import get_plaid_transfer_service, PlaidTransferService
from ..models.transfer import TransferQuote, MoneyTransfer
from ..auth.dependencies import get_current_user_id
from ..config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/plaid/transfers", tags=["plaid-transfers"])


class PlaidTransferQuoteRequest(BaseModel):
    """Request model for creating a transfer quote using Plaid account."""
    source_account_id: str = Field(..., description="Plaid account ID")
    beneficiary_id: str = Field(..., description="Beneficiary ID")
    amount: Decimal = Field(..., gt=0, description="Transfer amount")
    currency: str = Field(default="USD", description="Currency code")


class PlaidTransferInitiateRequest(BaseModel):
    """Request model for initiating a Plaid transfer."""
    quote_id: str = Field(..., description="Transfer quote ID")
    purpose: str = Field(..., min_length=1, max_length=200, description="Transfer purpose")
    reference: Optional[str] = Field(None, max_length=50, description="Optional reference")
    recipient_message: Optional[str] = Field(None, max_length=200, description="Message to recipient")


@router.post("/quote", response_model=dict)
async def create_plaid_transfer_quote(
    request: PlaidTransferQuoteRequest,
    user_id: str = Depends(get_current_user_id),
    service: PlaidTransferService = Depends(get_plaid_transfer_service)
):
    """
    Create a transfer quote using a Plaid-connected account.

    This endpoint validates the Plaid account, checks balance,
    and calculates fees for the transfer.
    """
    try:
        logger.info(f"Creating Plaid transfer quote for user {user_id}")

        quote = await service.create_transfer_quote(
            user_id=user_id,
            source_account_id=request.source_account_id,
            beneficiary_id=request.beneficiary_id,
            amount=request.amount,
            currency=request.currency
        )

        return {
            "success": True,
            "message": "Transfer quote created successfully",
            "data": {
                "quote": quote.dict()
            }
        }

    except Exception as e:
        logger.error(f"Failed to create transfer quote: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/initiate", response_model=dict)
async def initiate_plaid_transfer(
    request: PlaidTransferInitiateRequest,
    user_id: str = Depends(get_current_user_id),
    service: PlaidTransferService = Depends(get_plaid_transfer_service)
):
    """
    Initiate a money transfer using a Plaid-connected account.

    This endpoint processes the transfer through Plaid's Transfer API,
    moving money from the user's connected bank account to the beneficiary.
    """
    try:
        logger.info(f"Initiating Plaid transfer for user {user_id}")

        transfer = await service.initiate_plaid_transfer(
            user_id=user_id,
            quote_id=request.quote_id,
            purpose=request.purpose,
            reference=request.reference,
            recipient_message=request.recipient_message
        )

        return {
            "success": True,
            "message": "Transfer initiated successfully",
            "data": {
                "transfer": transfer.dict()
            }
        }

    except Exception as e:
        logger.error(f"Failed to initiate transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{transfer_id}/status", response_model=dict)
async def get_plaid_transfer_status(
    transfer_id: str,
    user_id: str = Depends(get_current_user_id),
    service: PlaidTransferService = Depends(get_plaid_transfer_service)
):
    """
    Get the status of a Plaid transfer.

    Returns the current status of the transfer, including
    real-time updates from Plaid if available.
    """
    try:
        logger.info(f"Getting transfer status for {transfer_id}")

        status_info = await service.get_transfer_status(
            user_id=user_id,
            transfer_id=transfer_id
        )

        return {
            "success": True,
            "message": "Transfer status retrieved successfully",
            "data": status_info
        }

    except Exception as e:
        logger.error(f"Failed to get transfer status: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/history", response_model=dict)
async def get_plaid_transfer_history(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: PlaidTransferService = Depends(get_plaid_transfer_service)
):
    """
    Get transfer history for Plaid-based transfers.

    Returns a paginated list of all transfers made using
    Plaid-connected accounts.
    """
    try:
        logger.info(f"Getting transfer history for user {user_id}")

        # This would need to be implemented in the service
        transfers = await service.repo.get_user_transfers(user_id)

        # Filter for Plaid transfers (those with Plaid account IDs as source)
        plaid_transfers = [
            t for t in transfers
            if t.source_account_id and t.source_account_id.startswith('plaid_')
        ]

        total = len(plaid_transfers)
        paginated = plaid_transfers[offset:offset + limit]

        return {
            "success": True,
            "message": "Transfer history retrieved successfully",
            "data": {
                "transfers": [t.dict() for t in paginated],
                "total_count": total,
                "limit": limit,
                "offset": offset
            }
        }

    except Exception as e:
        logger.error(f"Failed to get transfer history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
