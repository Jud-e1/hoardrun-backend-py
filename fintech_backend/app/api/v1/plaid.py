"""
Plaid API endpoints for bank account integration.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ...models.plaid import (
    PlaidLinkTokenRequest, PlaidLinkTokenResponse,
    PlaidExchangeTokenRequest, PlaidExchangeTokenResponse,
    PlaidAccount, PlaidTransaction, PlaidConnection,
    PlaidSyncRequest, PlaidSyncResponse
)
from ...services.plaid_service import get_plaid_service, PlaidService
from ...auth.dependencies import get_current_user_id, get_current_user
from ...config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/plaid", tags=["plaid"])


@router.post("/link-token", response_model=PlaidLinkTokenResponse)
async def create_link_token(
    request: PlaidLinkTokenRequest,
    user_id: str = Depends(get_current_user_id),
    service: PlaidService = Depends(get_plaid_service)
) -> PlaidLinkTokenResponse:
    """
    Create a Plaid Link token for connecting bank accounts.
    This creates an actual Plaid link session.
    """
    try:
        logger.info(f"Creating link token for user {user_id}")
        response = await service.create_link_token(user_id, request)
        return response
    except Exception as e:
        logger.error(f"Failed to create link token for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create link token: {str(e)}"
        )


@router.post("/exchange-token", response_model=PlaidExchangeTokenResponse)
async def exchange_public_token(
    request: PlaidExchangeTokenRequest,
    user_id: str = Depends(get_current_user_id),
    service: PlaidService = Depends(get_plaid_service)
) -> PlaidExchangeTokenResponse:
    """
    Exchange a public token for an access token and create connection.
    This establishes the actual connection with Plaid.
    """
    try:
        logger.info(f"Exchanging public token for user {user_id}")
        response = await service.exchange_public_token(user_id, request)
        return response
    except Exception as e:
        logger.error(f"Failed to exchange public token for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange token: {str(e)}"
        )


@router.post("/connections/{connection_id}/sync", response_model=PlaidSyncResponse)
async def sync_connection(
    connection_id: str,
    request: PlaidSyncRequest,
    user_id: str = Depends(get_current_user_id),
    service: PlaidService = Depends(get_plaid_service)
) -> PlaidSyncResponse:
    """
    Sync data for a Plaid connection.
    Fetches latest account balances and transactions from Plaid.
    """
    try:
        logger.info(f"Syncing connection {connection_id} for user {user_id}")
        response = await service.sync_connection(user_id, connection_id)
        return response
    except Exception as e:
        logger.error(f"Failed to sync connection {connection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync connection: {str(e)}"
        )


@router.get("/connections", response_model=List[PlaidConnection])
async def get_user_connections(
    user_id: str = Depends(get_current_user_id),
    service: PlaidService = Depends(get_plaid_service)
) -> List[PlaidConnection]:
    """
    Get all active Plaid connections for the authenticated user.
    """
    try:
        logger.info(f"Getting connections for user {user_id}")
        connections = await service.get_user_connections(user_id)
        return connections
    except Exception as e:
        logger.error(f"Failed to get connections for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connections: {str(e)}"
        )


@router.get("/accounts", response_model=List[PlaidAccount])
async def get_user_accounts(
    current_user: dict = Depends(get_current_user),
    service: PlaidService = Depends(get_plaid_service)
) -> List[PlaidAccount]:
    """
    Get all Plaid accounts for the authenticated user across all connections.
    Returns actual account data from Plaid with real-time balances.
    """
    try:
        user_id = current_user["user_id"]
        logger.info(f"Getting all accounts for user {user_id}")
        accounts = await service.get_user_accounts(user_id)
        return accounts
    except Exception as e:
        logger.error(f"Failed to get accounts for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get accounts: {str(e)}"
        )


@router.get("/connections/{connection_id}/accounts", response_model=List[PlaidAccount])
async def get_connection_accounts(
    connection_id: str,
    user_id: str = Depends(get_current_user_id),
    service: PlaidService = Depends(get_plaid_service)
) -> List[PlaidAccount]:
    """
    Get accounts for a specific connection with real-time balances.
    """
    try:
        logger.info(f"Getting accounts for connection {connection_id}")
        accounts = await service.get_connection_accounts(user_id, connection_id)
        return accounts
    except Exception as e:
        logger.error(f"Failed to get accounts for connection {connection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get accounts: {str(e)}"
        )


@router.get("/connections/{connection_id}/transactions", response_model=List[PlaidTransaction])
async def get_connection_transactions(
    connection_id: str,
    start_date: str = None,
    end_date: str = None,
    account_ids: str = None,
    user_id: str = Depends(get_current_user_id),
    service: PlaidService = Depends(get_plaid_service)
) -> List[PlaidTransaction]:
    """
    Get transactions for a specific connection from Plaid.
    """
    try:
        from datetime import date

        # Parse dates
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None

        # Parse account IDs
        account_id_list = account_ids.split(',') if account_ids else None

        logger.info(f"Getting transactions for connection {connection_id}")
        transactions = await service.get_connection_transactions(
            user_id=user_id,
            connection_id=connection_id,
            start_date=start,
            end_date=end,
            account_ids=account_id_list
        )
        return transactions
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to get transactions for connection {connection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get transactions: {str(e)}"
        )


@router.delete("/connections/{connection_id}")
async def disconnect_connection(
    connection_id: str,
    user_id: str = Depends(get_current_user_id),
    service: PlaidService = Depends(get_plaid_service)
):
    """
    Disconnect a Plaid connection and remove access.
    """
    try:
        logger.info(f"Disconnecting connection {connection_id} for user {user_id}")
        result = await service.disconnect_connection(user_id, connection_id)
        return result
    except Exception as e:
        logger.error(f"Failed to disconnect connection {connection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect connection: {str(e)}"
        )


@router.post("/webhook")
async def handle_plaid_webhook(
    request: dict,
    service: PlaidService = Depends(get_plaid_service)
):
    """
    Handle Plaid webhook events for real-time updates.
    """
    try:
        logger.info(f"Received Plaid webhook: {request.get('webhook_type')}")

        webhook_type = request.get('webhook_type')
        webhook_code = request.get('webhook_code')

        if webhook_type == 'TRANSACTIONS':
            if webhook_code == 'SYNC_UPDATES_AVAILABLE':
                item_id = request.get('item_id')
                logger.info(f"Transactions update for item {item_id}")
                # Trigger automatic sync
                await service.sync_item_by_id(item_id)

        elif webhook_type == 'ITEM':
            if webhook_code == 'LOGIN_REQUIRED':
                item_id = request.get('item_id')
                logger.warning(f"Item {item_id} requires re-authentication")
                await service.mark_item_needs_update(item_id)
            elif webhook_code == 'ERROR':
                item_id = request.get('item_id')
                error_code = request.get('error', {}).get('error_code')
                logger.error(f"Item {item_id} error: {error_code}")
                await service.mark_item_error(item_id, error_code)

        return {
            "status": "success",
            "message": "Webhook received and processed"
        }

    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/debit-card/link-token", response_model=PlaidLinkTokenResponse)
async def create_debit_card_link_token(
    user_id: str = Depends(get_current_user_id),
    service: PlaidService = Depends(get_plaid_service)
) -> PlaidLinkTokenResponse:
    """
    Create a Plaid Link token for debit card verification.
    This creates a link session specifically for verifying debit cards.
    """
    try:
        logger.info(f"Creating debit card link token for user {user_id}")
        response = await service.create_debit_card_link_token(user_id)
        return response
    except Exception as e:
        logger.error(f"Failed to create debit card link token for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create debit card link token: {str(e)}"
        )


@router.post("/debit-card/verify")
async def verify_plaid_debit_card(
    public_token: str,
    account_id: str = None,
    user_id: str = Depends(get_current_user_id),
    service: PlaidService = Depends(get_plaid_service)
):
    """
    Verify a debit card after Plaid Link flow completion.
    This exchanges the public token and verifies the debit card.
    """
    try:
        logger.info(f"Verifying debit card for user {user_id}")
        result = await service.verify_debit_card(
            user_id=user_id,
            public_token=public_token,
            account_id=account_id
        )
        return result
    except Exception as e:
        logger.error(f"Failed to verify debit card for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify debit card: {str(e)}"
        )


@router.get("/test-connection")
async def test_plaid_connection(
    service: PlaidService = Depends(get_plaid_service)
):
    """
    Test Plaid API connection.
    """
    try:
        logger.info("Testing Plaid API connection")
        result = await service.test_connection()
        return result
    except Exception as e:
        logger.error(f"Plaid connection test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection test failed: {str(e)}"
        )
    
    

# ─────────────────────────────────────────────────────────────────────────────
# Plaid Transfer routes (merged from plaid_transfers.py)
# Previously exposed as /plaid/transfers; now co-located with other Plaid routes.
# ─────────────────────────────────────────────────────────────────────────────
from typing import Optional  # noqa: E402 (already imported above, harmless)
from fastapi import Query  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from decimal import Decimal  # noqa: E402

from ...services.plaid_transfer_service import get_plaid_transfer_service, PlaidTransferService  # noqa: E402
from ...models.transfer import TransferQuote, MoneyTransfer  # noqa: E402


class PlaidTransferQuoteRequest(BaseModel):
    """Request model for creating a transfer quote using Plaid account."""
    source_account_id: str = Field(..., description="Plaid account ID")
    beneficiary_id: str = Field(..., description="Beneficiary ID")
    amount: Decimal = Field(..., gt=0, description="Transfer amount")
    currency: str = Field(default="USD", description="Currency code")


class PlaidTransferInitiateRequest(BaseModel):
    """Request model for initiating a Plaid transfer."""
    quote_id: str = Field(..., description="Transfer quote ID")
    purpose: str = Field(..., min_length=1, max_length=200)
    reference: Optional[str] = Field(None, max_length=50)
    recipient_message: Optional[str] = Field(None, max_length=200)


@router.post("/transfers/quote", response_model=dict, tags=["plaid-transfers"])
async def create_plaid_transfer_quote(
    request: PlaidTransferQuoteRequest,
    user_id: str = Depends(get_current_user_id),
    service: PlaidTransferService = Depends(get_plaid_transfer_service)
):
    """Create a transfer quote using a Plaid-connected account."""
    try:
        logger.info(f"Creating Plaid transfer quote for user {user_id}")
        quote = await service.create_transfer_quote(
            user_id=user_id,
            source_account_id=request.source_account_id,
            beneficiary_id=request.beneficiary_id,
            amount=request.amount,
            currency=request.currency
        )
        return {"success": True, "message": "Transfer quote created successfully",
                "data": {"quote": quote.dict()}}
    except Exception as e:
        logger.error(f"Failed to create transfer quote: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/transfers/initiate", response_model=dict, tags=["plaid-transfers"])
async def initiate_plaid_transfer(
    request: PlaidTransferInitiateRequest,
    user_id: str = Depends(get_current_user_id),
    service: PlaidTransferService = Depends(get_plaid_transfer_service)
):
    """Initiate a money transfer using a Plaid-connected account."""
    try:
        logger.info(f"Initiating Plaid transfer for user {user_id}")
        transfer = await service.initiate_plaid_transfer(
            user_id=user_id,
            quote_id=request.quote_id,
            purpose=request.purpose,
            reference=request.reference,
            recipient_message=request.recipient_message
        )
        return {"success": True, "message": "Transfer initiated successfully",
                "data": {"transfer": transfer.dict()}}
    except Exception as e:
        logger.error(f"Failed to initiate transfer: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/transfers/{transfer_id}/status", response_model=dict, tags=["plaid-transfers"])
async def get_plaid_transfer_status(
    transfer_id: str,
    user_id: str = Depends(get_current_user_id),
    service: PlaidTransferService = Depends(get_plaid_transfer_service)
):
    """Get the status of a Plaid transfer."""
    try:
        status_info = await service.get_transfer_status(user_id=user_id, transfer_id=transfer_id)
        return {"success": True, "message": "Transfer status retrieved", "data": status_info}
    except Exception as e:
        logger.error(f"Failed to get transfer status: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/transfers/history", response_model=dict, tags=["plaid-transfers"])
async def get_plaid_transfer_history(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: PlaidTransferService = Depends(get_plaid_transfer_service)
):
    """Get transfer history for Plaid-based transfers."""
    try:
        transfers = await service.repo.get_user_transfers(user_id)
        plaid_transfers = [t for t in transfers if t.source_account_id and t.source_account_id.startswith('plaid_')]
        total = len(plaid_transfers)
        paginated = plaid_transfers[offset:offset + limit]
        return {"success": True, "message": "Transfer history retrieved",
                "data": {"transfers": [t.dict() for t in paginated],
                         "total_count": total, "limit": limit, "offset": offset}}
    except Exception as e:
        logger.error(f"Failed to get transfer history: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
