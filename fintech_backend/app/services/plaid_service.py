"""
Plaid integration service for bank account connections.
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
    """Service for managing Plaid bank account integrations."""

    def __init__(self):
        self.repo = get_repository_manager()
        self.plaid_client = get_plaid_client()

    async def create_link_token(self, user_id: str, request: PlaidLinkTokenRequest) -> PlaidLinkTokenResponse:
        """
        Create a Plaid Link token for connecting bank accounts.

        Args:
            user_id: User identifier
            request: Link token creation request

        Returns:
            Link token response
        """
        logger.info(f"Creating Plaid link token for user {user_id}")

        # Validate user exists
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")

        try:
            # Create link token via Plaid client
            link_data = await self.plaid_client.create_link_token(
                user_id=user_id,
                client_name=request.client_name or "HoardRun"
            )

            # Store link token metadata in database for tracking
            link_token_id = str(uuid.uuid4())
            await self.repo.create_plaid_link_token({
                "link_token_id": link_token_id,
                "user_id": user_id,
                "link_token": link_data["link_token"],
                "expiration": link_data["expiration"],
                "created_at": datetime.utcnow(),
                "used": False
            })

            response = PlaidLinkTokenResponse(
                link_token=link_data["link_token"],
                expiration=link_data["expiration"],
                link_token_id=link_token_id
            )

            logger.info(f"Created link token {link_token_id} for user {user_id}")
            return response

        except Exception as e:
            logger.error(f"Failed to create link token for user {user_id}: {e}")
            raise ExternalServiceException(f"Plaid service error: {str(e)}")

    async def exchange_public_token(
        self,
        user_id: str,
        request: PlaidExchangeTokenRequest
    ) -> PlaidExchangeTokenResponse:
        """
        Exchange a public token for an access token and create connection.

        Args:
            user_id: User identifier
            request: Token exchange request

        Returns:
            Token exchange response with connection details
        """
        logger.info(f"Exchanging public token for user {user_id}")

        # Validate user exists
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")

        try:
            # Exchange public token for access token
            token_data = await self.plaid_client.exchange_public_token(request.public_token)

            # Mark link token as used
            if request.link_token_id:
                await self.repo.update_plaid_link_token_used(request.link_token_id)

            # Create Plaid connection record
            connection_id = str(uuid.uuid4())
            connection = PlaidConnection(
                connection_id=connection_id,
                user_id=user_id,
                item_id=token_data["item_id"],
                access_token=token_data["access_token"],
                status=PlaidConnectionStatus.ACTIVE,
                institution_id=None,  # Will be populated on first sync
                institution_name=None,
                created_at=datetime.utcnow(),
                last_synced_at=None,
                error_message=None
            )

            await self.repo.create_plaid_connection(connection)

            # Perform initial sync
            await self._sync_connection_data(connection)

            response = PlaidExchangeTokenResponse(
                connection_id=connection_id,
                access_token=token_data["access_token"],
                item_id=token_data["item_id"]
            )

            logger.info(f"Created Plaid connection {connection_id} for user {user_id}")
            return response

        except Exception as e:
            logger.error(f"Failed to exchange public token for user {user_id}: {e}")
            raise ExternalServiceException(f"Plaid service error: {str(e)}")

    async def sync_connection(self, user_id: str, connection_id: str) -> PlaidSyncResponse:
        """
        Sync data for a Plaid connection.

        Args:
            user_id: User identifier
            connection_id: Connection identifier

        Returns:
            Sync response with updated data counts
        """
        logger.info(f"Syncing Plaid connection {connection_id} for user {user_id}")

        # Get connection
        connection = await self.repo.get_plaid_connection(connection_id)
        if not connection:
            raise NotFoundError(f"Plaid connection {connection_id} not found")

        # Verify ownership
        if connection.user_id != user_id:
            raise BusinessLogicError("You don't have access to this connection")

        if connection.status != PlaidConnectionStatus.ACTIVE:
            raise BusinessLogicError("Connection is not active")

        try:
            # Perform sync
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

            logger.info(f"Synced {sync_result['accounts_synced']} accounts and {sync_result['transactions_synced']} transactions for connection {connection_id}")
            return response

        except Exception as e:
            logger.error(f"Failed to sync connection {connection_id}: {e}")

            # Update connection with error
            connection.status = PlaidConnectionStatus.ERROR
            connection.error_message = str(e)
            await self.repo.update_plaid_connection(connection)

            raise ExternalServiceException(f"Sync failed: {str(e)}")

    async def get_user_connections(self, user_id: str) -> List[PlaidConnection]:
        """
        Get all Plaid connections for a user.

        Args:
            user_id: User identifier

        Returns:
            List of user's Plaid connections
        """
        logger.info(f"Getting Plaid connections for user {user_id}")

        # Validate user exists
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")

        connections = await self.repo.get_user_plaid_connections(user_id)

        logger.info(f"Found {len(connections)} Plaid connections for user {user_id}")
        return connections

    async def get_connection_accounts(self, user_id: str, connection_id: str) -> List[PlaidAccount]:
        """
        Get accounts for a Plaid connection.

        Args:
            user_id: User identifier
            connection_id: Connection identifier

        Returns:
            List of accounts for the connection
        """
        logger.info(f"Getting accounts for connection {connection_id}")

        # Verify connection ownership
        connection = await self.repo.get_plaid_connection(connection_id)
        if not connection or connection.user_id != user_id:
            raise NotFoundError("Connection not found or access denied")

        accounts = await self.repo.get_plaid_accounts(connection_id)

        logger.info(f"Found {len(accounts)} accounts for connection {connection_id}")
        return accounts

    async def get_connection_transactions(
        self,
        user_id: str,
        connection_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        account_ids: Optional[List[str]] = None
    ) -> List[PlaidTransaction]:
        """
        Get transactions for a Plaid connection.

        Args:
            user_id: User identifier
            connection_id: Connection identifier
            start_date: Optional start date filter
            end_date: Optional end date filter
            account_ids: Optional account ID filters

        Returns:
            List of transactions
        """
        logger.info(f"Getting transactions for connection {connection_id}")

        # Verify connection ownership
        connection = await self.repo.get_plaid_connection(connection_id)
        if not connection or connection.user_id != user_id:
            raise NotFoundError("Connection not found or access denied")

        # Default date range (last 30 days)
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        transactions = await self.repo.get_plaid_transactions(
            connection_id=connection_id,
            start_date=start_date,
            end_date=end_date,
            account_ids=account_ids
        )

        logger.info(f"Found {len(transactions)} transactions for connection {connection_id}")
        return transactions

    async def disconnect_connection(self, user_id: str, connection_id: str) -> Dict[str, Any]:
        """
        Disconnect a Plaid connection.

        Args:
            user_id: User identifier
            connection_id: Connection identifier

        Returns:
            Disconnect confirmation
        """
        logger.info(f"Disconnecting Plaid connection {connection_id} for user {user_id}")

        # Get connection
        connection = await self.repo.get_plaid_connection(connection_id)
        if not connection:
            raise NotFoundError(f"Plaid connection {connection_id} not found")

        # Verify ownership
        if connection.user_id != user_id:
            raise BusinessLogicError("You don't have access to this connection")

        try:
            # Remove item from Plaid
            await self.plaid_client.remove_item(connection.access_token)

            # Update connection status
            connection.status = PlaidConnectionStatus.DISCONNECTED
            await self.repo.update_plaid_connection(connection)

            # Optionally remove associated data
            # await self.repo.remove_plaid_connection_data(connection_id)

            logger.info(f"Successfully disconnected Plaid connection {connection_id}")
            return {
                "connection_id": connection_id,
                "status": "disconnected",
                "disconnected_at": datetime.utcnow()
            }

        except Exception as e:
            logger.error(f"Failed to disconnect connection {connection_id}: {e}")
            raise ExternalServiceException(f"Disconnect failed: {str(e)}")

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test Plaid API connection.

        Returns:
            Connection test results
        """
        logger.info("Testing Plaid API connection")

        try:
            result = await self.plaid_client.test_connection()
            return result
        except Exception as e:
            logger.error(f"Plaid connection test failed: {e}")
            return {
                "status": "error",
                "message": f"Connection test failed: {str(e)}"
            }

    async def _sync_connection_data(self, connection: PlaidConnection) -> Dict[str, int]:
        """
        Sync account and transaction data for a connection.

        Args:
            connection: Plaid connection object

        Returns:
            Sync statistics
        """
        accounts_synced = 0
        transactions_synced = 0

        try:
            # Get accounts from Plaid
            plaid_accounts = await self.plaid_client.get_accounts(connection.access_token)

            # Sync accounts
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

            # Get transactions from Plaid (last 30 days)
            start_date = (date.today() - timedelta(days=30)).isoformat()
            end_date = date.today().isoformat()

            plaid_transactions = await self.plaid_client.get_transactions(
                access_token=connection.access_token,
                start_date=start_date,
                end_date=end_date
            )

            # Sync transactions
            for transaction_data in plaid_transactions:
                transaction = PlaidTransaction(
                    transaction_id=transaction_data["transaction_id"],
                    account_id=transaction_data["account_id"],
                    connection_id=connection.connection_id,
                    amount=Decimal(str(transaction_data["amount"])),
                    iso_currency_code=transaction_data.get("iso_currency_code"),
                    unofficial_currency_code=transaction_data.get("unofficial_currency_code"),
                    date=transaction_data["date"],
                    authorized_date=transaction_data.get("authorized_date"),
                    name=transaction_data["name"],
                    merchant_name=transaction_data.get("merchant_name"),
                    payment_channel=transaction_data.get("payment_channel"),
                    pending=transaction_data.get("pending", False),
                    pending_transaction_id=transaction_data.get("pending_transaction_id"),
                    account_owner=transaction_data.get("account_owner"),
                    transaction_type=transaction_data.get("transaction_type"),
                    payment_meta=transaction_data.get("payment_meta"),
                    location=transaction_data.get("location"),
                    transaction_code=transaction_data.get("transaction_code"),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )

                await self.repo.upsert_plaid_transaction(transaction)
                transactions_synced += 1

            # Update institution info if available
            if plaid_accounts and len(plaid_accounts) > 0:
                # Get institution info (mock for now)
                connection.institution_name = "Test Bank"  # Would come from Plaid API

            logger.info(f"Synced {accounts_synced} accounts and {transactions_synced} transactions for connection {connection.connection_id}")

        except Exception as e:
            logger.error(f"Error syncing data for connection {connection.connection_id}: {e}")
            raise

        return {
            "accounts_synced": accounts_synced,
            "transactions_synced": transactions_synced
        }


# Dependency provider
def get_plaid_service() -> PlaidService:
    """Dependency provider for Plaid service."""
    return PlaidService()
