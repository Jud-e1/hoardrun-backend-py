"""
Plaid Transfer Service for bank account money transfers.
"""

import uuid
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any

from ..models.transfer import (
    TransferQuote, TransferQuoteRequest, TransferInitiateRequest,
    MoneyTransfer, TransferStatus, TransferType, TransferPriority
)
from ..models.plaid import PlaidConnectionStatus
from ..core.exceptions import (
    ValidationError, NotFoundError, BusinessLogicError,
    ExternalServiceException
)
from ..data.repository import get_repository_manager
from ..external.plaid_client import get_plaid_client
from ..utils.validators import validate_user_exists
from ..config.logging import get_logger

logger = get_logger(__name__)


class PlaidTransferService:
    """Service for managing money transfers via Plaid."""

    def __init__(self):
        self.repo = get_repository_manager()
        self.plaid_client = get_plaid_client()

    async def create_transfer_quote(
        self,
        user_id: str,
        request: TransferQuoteRequest
    ) -> TransferQuote:
        """
        Create a transfer quote for Plaid transfers.

        Args:
            user_id: User identifier
            request: Transfer quote request

        Returns:
            Transfer quote with fees and rates
        """
        logger.info(f"Creating transfer quote for user {user_id}")

        # Validate user exists
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")

        # Validate Plaid account ownership
        plaid_account = await self.repo.plaid_accounts.get_by_id(request.source_account_id)
        if not plaid_account:
            raise NotFoundError("Plaid account not found")

        connection = await self.repo.plaid_connections.get_by_id(plaid_account["connection_id"])
        if not connection or connection["user_id"] != user_id:
            raise BusinessLogicError("You don't have access to this account")

        if connection["status"] != PlaidConnectionStatus.ACTIVE.value:
            raise BusinessLogicError("Plaid connection is not active")

        # Get beneficiary details
        beneficiary = await self.repo.beneficiaries.get_by_id(request.beneficiary_id)
        if not beneficiary or beneficiary["user_id"] != user_id:
            raise NotFoundError("Beneficiary not found")

        # Calculate fees (simplified for Plaid transfers)
        transfer_fee = Decimal("2.99")  # Fixed fee for Plaid transfers
        exchange_fee = Decimal("0.00")  # No exchange fee for same currency
        total_fees = transfer_fee + exchange_fee

        # For now, assume USD only
        if request.source_currency != "USD":
            raise ValidationError("Only USD transfers supported currently")

        # Create quote
        quote = TransferQuote(
            quote_id=str(uuid.uuid4()),
            from_amount=request.source_amount,
            from_currency=request.source_currency,
            to_amount=request.source_amount,  # Same amount for same currency
            to_currency=request.source_currency,
            exchange_rate=None,  # No exchange for same currency
            transfer_fee=transfer_fee,
            exchange_fee=exchange_fee,
            total_fees=total_fees,
            total_cost=request.source_amount + total_fees,
            expires_at=datetime.utcnow() + timedelta(minutes=15),
            transfer_type=TransferType.INSTANT_TRANSFER
        )

        # Store quote in repository
        await self.repo.transfers.create({
            "id": quote.quote_id,
            "user_id": user_id,
            "source_account_id": request.source_account_id,
            "beneficiary_id": request.beneficiary_id,
            "from_amount": float(quote.from_amount),
            "from_currency": quote.from_currency,
            "to_amount": float(quote.to_amount),
            "to_currency": quote.to_currency,
            "transfer_fee": float(quote.transfer_fee),
            "exchange_fee": float(quote.exchange_fee),
            "total_fees": float(quote.total_fees),
            "total_cost": float(quote.total_cost),
            "expires_at": quote.expires_at.isoformat(),
            "transfer_type": quote.transfer_type.value,
            "quote_type": "plaid_transfer"
        })

        logger.info(f"Created transfer quote {quote.quote_id} for user {user_id}")
        return quote

    async def initiate_transfer(
        self,
        user_id: str,
        quote_id: str,
        request: TransferInitiateRequest
    ) -> MoneyTransfer:
        """
        Initiate a Plaid transfer using a quote.

        Args:
            user_id: User identifier
            quote_id: Quote identifier
            request: Transfer initiation request

        Returns:
            Money transfer object
        """
        logger.info(f"Initiating Plaid transfer for user {user_id} with quote {quote_id}")

        # Validate user exists
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")

        # Get and validate quote
        quote_data = await self.repo.transfers.get_by_id(quote_id)
        if not quote_data:
            raise NotFoundError("Quote not found or expired")

        if quote_data["user_id"] != user_id:
            raise BusinessLogicError("You don't have access to this quote")

        if datetime.fromisoformat(quote_data["expires_at"]) < datetime.utcnow():
            raise BusinessLogicError("Quote has expired")

        # Get Plaid account and connection
        plaid_account = await self.repo.plaid_accounts.get_by_id(quote_data["source_account_id"])
        if not plaid_account:
            raise NotFoundError("Plaid account not found")

        connection = await self.repo.plaid_connections.get_by_id(plaid_account["connection_id"])
        if not connection or connection["status"] != PlaidConnectionStatus.ACTIVE.value:
            raise BusinessLogicError("Plaid connection is not active")

        # Get beneficiary
        beneficiary = await self.repo.beneficiaries.get_by_id(quote_data["beneficiary_id"])
        if not beneficiary:
            raise NotFoundError("Beneficiary not found")

        try:
            # Create transfer via Plaid
            transfer_request = {
                "access_token": connection["access_token"],
                "account_id": plaid_account["account_id"],
                "amount": float(quote_data["from_amount"]),
                "description": request.purpose or f"Transfer to {beneficiary['first_name']} {beneficiary['last_name']}",
                "ach_class": "ppd",
                "user": {
                    "legal_name": f"{beneficiary['first_name']} {beneficiary['last_name']}"
                }
            }

            plaid_response = await self.plaid_client.create_transfer(transfer_request)

            # Create transfer record
            transfer = MoneyTransfer(
                transfer_id=str(uuid.uuid4()),
                user_id=user_id,
                source_account_id=quote_data["source_account_id"],
                beneficiary_id=quote_data["beneficiary_id"],
                transfer_type=TransferType.INSTANT_TRANSFER,
                status=TransferStatus.PROCESSING,
                priority=TransferPriority.STANDARD,
                source_amount=Decimal(str(quote_data["from_amount"])),
                source_currency=quote_data["from_currency"],
                destination_amount=Decimal(str(quote_data["to_amount"])),
                destination_currency=quote_data["to_currency"],
                exchange_rate_used=None,
                transfer_fee=Decimal(str(quote_data["transfer_fee"])),
                exchange_fee=Decimal(str(quote_data["exchange_fee"])),
                total_fees=Decimal(str(quote_data["total_fees"])),
                total_cost=Decimal(str(quote_data["total_cost"])),
                purpose=request.purpose,
                reference=request.reference,
                recipient_message=request.recipient_message,
                quote_id=quote_id,
                external_reference=plaid_response["transfer_id"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                status_history=[{"status": "processing", "at": datetime.utcnow().isoformat()}],
                compliance_check_passed=True,
                requires_documents=False,
            )

            # Store transfer
            await self.repo.transfers.create({
                "id": transfer.transfer_id,
                "user_id": transfer.user_id,
                "source_account_id": transfer.source_account_id,
                "beneficiary_id": transfer.beneficiary_id,
                "transfer_type": transfer.transfer_type.value,
                "status": transfer.status.value,
                "priority": transfer.priority.value,
                "source_amount": float(transfer.source_amount),
                "source_currency": transfer.source_currency,
                "destination_amount": float(transfer.destination_amount),
                "destination_currency": transfer.destination_currency,
                "transfer_fee": float(transfer.transfer_fee),
                "exchange_fee": float(transfer.exchange_fee),
                "total_fees": float(transfer.total_fees),
                "total_cost": float(transfer.total_cost),
                "purpose": transfer.purpose,
                "reference": transfer.reference,
                "recipient_message": transfer.recipient_message,
                "quote_id": transfer.quote_id,
                "external_reference": transfer.external_reference,
                "status_history": transfer.status_history,
                "compliance_check_passed": transfer.compliance_check_passed,
                "requires_documents": transfer.requires_documents,
                "plaid_transfer_id": plaid_response["transfer_id"],
                "transfer_type": "plaid"
            })

            logger.info(f"Initiated Plaid transfer {transfer.transfer_id} for user {user_id}")
            return transfer

        except Exception as e:
            logger.error(f"Failed to initiate Plaid transfer for user {user_id}: {e}")
            raise ExternalServiceException(f"Plaid transfer failed: {str(e)}")

    async def get_transfer_status(self, user_id: str, transfer_id: str) -> Dict[str, Any]:
        """
        Get the status of a Plaid transfer.

        Args:
            user_id: User identifier
            transfer_id: Transfer identifier

        Returns:
            Transfer status information
        """
        logger.info(f"Getting transfer status for transfer {transfer_id}")

        # Get transfer record
        transfer_data = await self.repo.transfers.get_by_id(transfer_id)
        if not transfer_data or transfer_data["user_id"] != user_id:
            raise NotFoundError("Transfer not found")

        if transfer_data.get("transfer_type") != "plaid":
            raise BusinessLogicError("Not a Plaid transfer")

        plaid_transfer_id = transfer_data.get("plaid_transfer_id")
        if not plaid_transfer_id:
            raise BusinessLogicError("Plaid transfer ID not found")

        try:
            # Get status from Plaid
            status_response = await self.plaid_client.get_transfer_status(plaid_transfer_id)

            # Update local status if changed
            current_status = transfer_data["status"]
            new_status = status_response["status"]

            if current_status != new_status:
                transfer_data["status"] = new_status
                transfer_data["status_history"].append({
                    "status": new_status,
                    "at": datetime.utcnow().isoformat()
                })

                if new_status == "completed":
                    transfer_data["completed_at"] = status_response.get("settled_at")
                elif new_status == "failed":
                    transfer_data["failure_reason"] = status_response.get("failure_reason")

                await self.repo.transfers.update(transfer_id, transfer_data)

            logger.info(f"Retrieved status for transfer {transfer_id}: {new_status}")
            return {
                "transfer_id": transfer_id,
                "status": new_status,
                "amount": status_response["amount"],
                "description": status_response["description"],
                "created_at": status_response["created_at"],
                "posted_at": status_response.get("posted_at"),
                "settled_at": status_response.get("settled_at"),
                "failure_reason": status_response.get("failure_reason"),
                "last_updated": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get transfer status for {transfer_id}: {e}")
            raise ExternalServiceException(f"Status check failed: {str(e)}")

    async def cancel_transfer(self, user_id: str, transfer_id: str) -> Dict[str, Any]:
        """
        Cancel a Plaid transfer.

        Args:
            user_id: User identifier
            transfer_id: Transfer identifier

        Returns:
            Cancellation confirmation
        """
        logger.info(f"Cancelling transfer {transfer_id} for user {user_id}")

        # Get transfer record
        transfer_data = await self.repo.transfers.get_by_id(transfer_id)
        if not transfer_data or transfer_data["user_id"] != user_id:
            raise NotFoundError("Transfer not found")

        if transfer_data.get("transfer_type") != "plaid":
            raise BusinessLogicError("Not a Plaid transfer")

        current_status = transfer_data["status"]
        if current_status in ["completed", "failed", "cancelled"]:
            raise BusinessLogicError("Transfer cannot be cancelled")

        # Note: Plaid transfers may not be cancellable once initiated
        # This would need to be implemented based on Plaid's cancellation API
        # For now, we'll mark as cancelled locally
        transfer_data["status"] = "cancelled"
        transfer_data["status_history"].append({
            "status": "cancelled",
            "at": datetime.utcnow().isoformat(),
            "reason": "User requested cancellation"
        })

        await self.repo.transfers.update(transfer_id, transfer_data)

        logger.info(f"Cancelled transfer {transfer_id}")
        return {
            "transfer_id": transfer_id,
            "status": "cancelled",
            "cancelled_at": datetime.utcnow().isoformat()
        }

    async def list_user_transfers(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List Plaid transfers for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of transfers to return
            offset: Number of transfers to skip

        Returns:
            List of transfer records
        """
        logger.info(f"Listing Plaid transfers for user {user_id}")

        # Validate user exists
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")

        # Get transfers with Plaid type
        all_transfers = await self.repo.transfers.get_by_user_id(user_id)
        plaid_transfers = [
            t for t in all_transfers
            if t.get("transfer_type") == "plaid"
        ]

        # Sort by creation date (most recent first)
        plaid_transfers.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return plaid_transfers[offset:offset + limit]


# Dependency provider
def get_plaid_transfer_service() -> PlaidTransferService:
    """Dependency provider for Plaid transfer service."""
    return PlaidTransferService()
