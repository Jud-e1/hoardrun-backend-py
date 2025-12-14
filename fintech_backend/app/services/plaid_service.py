"""
Plaid integration service for bank account connections.
This service handles ACTUAL Plaid API calls for real bank connections.
"""

import uuid
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

from ..models.plaid import (
    PlaidLinkTokenRequest, PlaidLinkTokenResponse,
    PlaidExchangeTokenRequest, PlaidExchangeTokenResponse,
    PlaidAccount, PlaidTransaction, PlaidConnection,
    PlaidConnectionStatus, PlaidSyncRequest, PlaidSyncResponse
)
from ..core.exceptions import (
    ValidationError, NotFoundError, BusinessLogicError,
    ExternalServiceException
)
from ..data.repository import get_repository_manager
from ..external.plaid_client import get_plaid_client
from ..utils.validators import validate_user_exists
from ..config.logging import get_logger

logger = get_logger(__name__)


class PlaidService:
    """Service for managing REAL Plaid bank account integrations."""

    def __init__(self):
        self.repo = get_repository_manager()
        self.plaid_client = get_plaid_client()

    async def create_link_token(self, user_id: str, request: PlaidLinkTokenRequest) -> PlaidLinkTokenResponse:
        """
        Create a Plaid Link token for connecting bank accounts.
        This creates an ACTUAL Plaid link session.
        """
        logger.info(f"Creating REAL Plaid link token for user {user_id}")

        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")

        try:
            # Create REAL link token via Plaid API
            link_data = await self.plaid_client.create_link_token(
                user_id=user_id,
                client_name=request.client_name or "HoardRun",
                products=request.products or ["auth", "transactions"],
                country_codes=request.country_codes or ["US"],
                language=request.language or "en",
                webhook=request.webhook_url
            )

            # Store link token metadata for tracking
            link_token_id = str(uuid.uuid4())
            await self.repo.create_plaid_link_token({
                "link_token_id": link_token_id,
                "user_id": user_id,
                "link_token": link_data["link_token"],
                "expiration": link_data["expiration"],
                "request_id": link_data.get("request_id"),
                "created_at": datetime.utcnow(),
                "used": False
            })

            response = PlaidLinkTokenResponse(
                link_token=link_data["link_token"],
                expiration=link_data["expiration"],
                link_token_id=link_token_id,
                request_id=link_data.get("request_id")
            )

            logger.info(f"Created REAL Plaid link token {link_token_id} for user {user_id}")
            return response

        except Exception as e:
            logger.error(f"Failed to create Plaid link token for user {user_id}: {e}")
            raise ExternalServiceException(f"Plaid service error: {str(e)}")

    async def exchange_public_token(
        self,
        user_id: str,
        request: PlaidExchangeTokenRequest
    ) -> PlaidExchangeTokenResponse:
        """
        Exchange a public token for an access token.
        This establishes a REAL connection with the user's bank via Plaid.
        """
        logger.info(f"Exchanging REAL Plaid public token for user {user_id}")

        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")

        try:
            # Exchange public token for REAL access token via Plaid API
            token_data = await self.plaid_client.exchange_public_token(request.public_token)

            # Mark link token as used if provided
            if request.link_token_id:
                await self.repo.update_plaid_link_token_used(request.link_token_id)

            # Get REAL institution information
            item_data = await self.plaid_client.get_item(token_data["access_token"])
            institution_id = item_data.get("institution_id")
            
            # Fetch institution name
            institution_name = None
            if institution_id:
                institution_info = await self.plaid_client.get_institution(institution_id)
                institution_name = institution_info.get("name")

            # Create Plaid connection record with REAL data
            connection_id = str(uuid.uuid4())
            connection = PlaidConnection(
                connection_id=connection_id,
                user_id=user_id,
                item_id=token_data["item_id"],
                access_token=token_data["access_token"],
                status=PlaidConnectionStatus.ACTIVE,
                institution_id=institution_id,
                institution_name=institution_name,
                created_at=datetime.utcnow(),
                last_synced_at=None,
                error_message=None
            )

            await self.repo.create_plaid_connection(connection)

            # Perform initial sync to get REAL account data
            await self._sync_connection_data(connection)

            response = PlaidExchangeTokenResponse(
                connection_id=connection_id,
                access_token=token_data["access_token"],
                item_id=token_data["item_id"]
            )

            logger.info(f"Created REAL Plaid connection {connection_id} for user {user_id}")
            return response

        except Exception as e:
            logger.error(f"Failed to exchange Plaid token for user {user_id}: {e}")
            raise ExternalServiceException(f"Plaid service error: {str(e)}")

    async def sync_connection(self, user_id: str, connection_id: str) -> PlaidSyncResponse:
        """
        Sync REAL data from Plaid for a connection.
        Fetches latest balances and transactions.
        """
        logger.info(f"Syncing REAL Plaid connection {connection_id} for user {user_id}")

        connection = await self.repo.get_plaid_connection(connection_id)
        if not connection:
            raise NotFoundError(f"Plaid connection {connection_id} not found")

        if connection.user_id != user_id:
            raise BusinessLogicError("You don't have access to this connection")

        if connection.status != PlaidConnectionStatus.ACTIVE:
            raise BusinessLogicError("Connection is not active")

        try:
            # Perform REAL sync with Plaid API
            sync_result = await self._sync_connection_data(connection)

            # Update last synced timestamp
            connection.last_synced_at = datetime.utcnow()
            await self.repo.update_plaid_connection(connection)

            response = PlaidSyncResponse(
                connection_id=connection_id,
                accounts_synced=sync_result["accounts_synced"],
                transactions_synced=sync_result["transactions_synced"],
                last_synced_at=connection.last_synced_at
            )

            logger.info(f"Synced {sync_result['accounts_synced']} accounts and {sync_result['transactions_synced']} transactions")
            return response

        except Exception as e:
            logger.error(f"Failed to sync connection {connection_id}: {e}")

            # Update connection with error
            connection.status = PlaidConnectionStatus.ERROR
            connection.error_message = str(e)
            await self.repo.update_plaid_connection(connection)

            raise ExternalServiceException(f"Sync failed: {str(e)}")

    async def get_user_connections(self, user_id: str) -> List[PlaidConnection]:
        """Get all ACTIVE Plaid connections for a user."""
        logger.info(f"Getting REAL Plaid connections for user {user_id}")

        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")

        connections = await self.repo.get_user_plaid_connections(user_id)
        
        # Only return active connections
        active_connections = [c for c in connections if c.status == PlaidConnectionStatus.ACTIVE]

        logger.info(f"Found {len(active_connections)} active Plaid connections for user {user_id}")
        return active_connections

    async def get_user_accounts(self, user_id: str) -> List[PlaidAccount]:
        """
        Get all REAL Plaid accounts for a user across all connections.
        Returns actual bank account data from Plaid.
        """
        logger.info(f"Getting all REAL Plaid accounts for user {user_id}")

        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")

        # Get all active connections
        connections = await self.repo.get_user_plaid_connections(user_id)
        active_connections = [conn for conn in connections if conn.status == PlaidConnectionStatus.ACTIVE]

        if not active_connections:
            logger.info(f"No active Plaid connections found for user {user_id}")
            return []

        # Aggregate REAL accounts from all active connections
        all_accounts = []
        for connection in active_connections:
            # Sync latest data from Plaid before returning
            try:
                await self._sync_connection_data(connection)
            except Exception as e:
                logger.warning(f"Failed to sync connection {connection.connection_id}: {e}")
                continue

            accounts = await self.repo.get_plaid_accounts(connection.connection_id)
            all_accounts.extend(accounts)

        logger.info(f"Found {len(all_accounts)} REAL Plaid accounts for user {user_id}")
        return all_accounts

    async def disconnect_connection(self, user_id: str, connection_id: str) -> Dict[str, Any]:
        """Disconnect a REAL Plaid connection."""
        logger.info(f"Disconnecting REAL Plaid connection {connection_id} for user {user_id}")

        connection = await self.repo.get_plaid_connection(connection_id)
        if not connection:
            raise NotFoundError(f"Plaid connection {connection_id} not found")

        if connection.user_id != user_id:
            raise BusinessLogicError("You don't have access to this connection")

        try:
            # Remove item from Plaid (REAL disconnection)
            await self.plaid_client.remove_item(connection.access_token)

            # Update connection status
            connection.status = PlaidConnectionStatus.DISCONNECTED
            await self.repo.update_plaid_connection(connection)

            logger.info(f"Successfully disconnected REAL Plaid connection {connection_id}")
            return {
                "connection_id": connection_id,
                "status": "disconnected",
                "disconnected_at": datetime.utcnow()
            }

        except Exception as e:
            logger.error(f"Failed to disconnect connection {connection_id}: {e}")
            raise ExternalServiceException(f"Disconnect failed: {str(e)}")

    async def _sync_connection_data(self, connection: PlaidConnection) -> Dict[str, int]:
        """
        Sync REAL account and transaction data from Plaid.
        This fetches actual data from the user's bank.
        """
        accounts_synced = 0
        transactions_synced = 0

        try:
            # Get REAL accounts from Plaid API
            plaid_accounts = await self.plaid_client.get_accounts(connection.access_token)

            # Sync REAL account data
            for account_data in plaid_accounts:
                account = PlaidAccount(
                    account_id=account_data["account_id"],
                    connection_id=connection.connection_id,
                    name=account_data["name"],
                    official_name=account_data.get("official_name"),
                    type=account_data.get("type"),
                    subtype=account_data.get("subtype"),
                    mask=account_data.get("mask"),
                    balances=account_data.get("balances"),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )

                await self.repo.upsert_plaid_account(account)
                accounts_synced += 1

            # Get REAL transactions from Plaid API
            start_date = (date.today() - timedelta(days=30)).isoformat()
            end_date = date.today().isoformat()

            plaid_transactions = await self.plaid_client.get_transactions(
                access_token=connection.access_token,
                start_date=start_date,
                end_date=end_date
            )

            # Sync REAL transaction data
            for transaction_data in plaid_transactions:
                transaction = PlaidTransaction(
                    transaction_id=transaction_data["transaction_id"],
                    account_id=transaction_data["account_id"],
                    connection_id=connection.connection_id,
                    amount=Decimal(str(transaction_data["amount"])),
                    iso_currency_code=transaction_data.get("iso_currency_code"),
                    date=transaction_data["date"],
                    name=transaction_data["name"],
                    merchant_name=transaction_data.get("merchant_name"),
                    pending=transaction_data.get("pending", False),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )

                await self.repo.upsert_plaid_transaction(transaction)
                transactions_synced += 1

            # Update institution info
            if plaid_accounts:
                item_data = await self.plaid_client.get_item(connection.access_token)
                if item_data.get("institution_id"):
                    institution_info = await self.plaid_client.get_institution(item_data["institution_id"])
                    connection.institution_name = institution_info.get("name")

            logger.info(f"Synced {accounts_synced} accounts and {transactions_synced} transactions")

        except Exception as e:
            logger.error(f"Error syncing REAL data for connection {connection.connection_id}: {e}")
            raise

        return {
            "accounts_synced": accounts_synced,
            "transactions_synced": transactions_synced
        }

    async def mark_item_needs_update(self, item_id: str):
        """Mark connection as needing re-authentication."""
        connection = await self.repo.get_plaid_connection_by_item_id(item_id)
        if connection:
            connection.status = PlaidConnectionStatus.NEEDS_UPDATE
            await self.repo.update_plaid_connection(connection)

    async def mark_item_error(self, item_id: str, error_code: str):
        """Mark connection as having an error."""
        connection = await self.repo.get_plaid_connection_by_item_id(item_id)
        if connection:
            connection.status = PlaidConnectionStatus.ERROR
            connection.error_message = error_code
            await self.repo.update_plaid_connection(connection)

    async def sync_item_by_id(self, item_id: str):
        """Sync a connection by item ID (for webhooks)."""
        connection = await self.repo.get_plaid_connection_by_item_id(item_id)
        if connection:
            await self._sync_connection_data(connection)

    async def create_debit_card_link_token(self, user_id: str) -> PlaidLinkTokenResponse:
        """
        Create a Plaid Link token for debit card verification.
        This creates a link session specifically for verifying debit cards.
        """
        logger.info(f"Creating debit card link token for user {user_id}")

        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")

        try:
            # Create debit card verification link token via Plaid API
            link_data = await self.plaid_client.create_debit_card_link_token(
                user_id=user_id,
                client_name="HoardRun"
            )

            # Store link token metadata for tracking
            link_token_id = str(uuid.uuid4())
            await self.repo.create_plaid_link_token({
                "link_token_id": link_token_id,
                "user_id": user_id,
                "link_token": link_data["link_token"],
                "expiration": link_data["expiration"],
                "request_id": link_data.get("request_id"),
                "created_at": datetime.utcnow(),
                "used": False
            })

            response = PlaidLinkTokenResponse(
                link_token=link_data["link_token"],
                expiration=link_data["expiration"],
                link_token_id=link_token_id,
                request_id=link_data.get("request_id")
            )

            logger.info(f"Created debit card link token {link_token_id} for user {user_id}")
            return response

        except Exception as e:
            logger.error(f"Failed to create debit card link token for user {user_id}: {e}")
            raise ExternalServiceException(f"Plaid service error: {str(e)}")

    async def verify_debit_card(
        self,
        user_id: str,
        public_token: str,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify a debit card using Plaid.
        This exchanges the public token and verifies the debit card account.
        """
        logger.info(f"Verifying debit card for user {user_id}")

        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")

        try:
            # Verify debit card via Plaid API
            verification_data = await self.plaid_client.verify_debit_card(
                public_token=public_token,
                account_id=account_id
            )

            # Mark link token as used if provided (would need to track this)
            # For now, we'll assume the verification was successful

            # Create a payment method record for the verified debit card
            payment_method_data = {
                "user_id": user_id,
                "type": "debit_card",
                "provider": "plaid",
                "account_id": verification_data["account_id"],
                "account_name": verification_data["account_name"],
                "account_type": verification_data["account_type"],
                "account_subtype": verification_data["account_subtype"],
                "access_token": verification_data["access_token"],
                "item_id": verification_data["item_id"],
                "status": "verified",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            # Store in payment methods (assuming payment_methods_service integration)
            # For now, we'll return the verification data
            # In a full implementation, you'd integrate with payment_methods_service

            logger.info(f"Successfully verified debit card for user {user_id}")
            return {
                "verified": True,
                "account_id": verification_data["account_id"],
                "account_name": verification_data["account_name"],
                "account_type": verification_data["account_type"],
                "account_subtype": verification_data["account_subtype"],
                "payment_method_data": payment_method_data
            }

        except Exception as e:
            logger.error(f"Failed to verify debit card for user {user_id}: {e}")
            raise ExternalServiceException(f"Plaid service error: {str(e)}")

    async def test_connection(self) -> Dict[str, Any]:
        """Test REAL Plaid API connection."""
        logger.info("Testing REAL Plaid API connection")

        try:
            result = await self.plaid_client.test_connection()
            return result
        except Exception as e:
            logger.error(f"Plaid connection test failed: {e}")
            return {
                "status": "error",
                "message": f"Connection test failed: {str(e)}"
            }


def get_plaid_service() -> PlaidService:
    """Dependency provider for Plaid service."""
    return PlaidService()

