"""
Plaid API endpoints for bank account integration.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..models.plaid import (
    PlaidLinkTokenRequest, PlaidLinkTokenResponse,
    PlaidExchangeTokenRequest, PlaidExchangeTokenResponse,
    PlaidAccount, PlaidTransaction, PlaidConnection,
    PlaidSyncRequest, PlaidSyncResponse
)
from ..services.plaid_service import get_plaid_service, PlaidService
from ..auth.dependencies import get_current_user_id, get_current_user
from ..config.logging import get_logger

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
    
    