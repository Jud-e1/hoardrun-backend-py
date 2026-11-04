"""
Plaid Transfer Service for bank account money transfers.

Plaid Transfer debits the sender's linked account. Nothing in this codebase pays the
recipient out yet, so initiating a transfer stays off unless ENABLE_PLAID_TRANSFERS=true:
turned on without a payout step, it would take money that never arrives.
"""

import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from ..models.plaid import PlaidConnectionStatus
from ..models.transfer import (
    MoneyTransfer, TransferInitiateRequest, TransferPriority, TransferQuote,
    TransferQuoteRequest, TransferStatus, TransferType
)
from ..core.exceptions import ExternalServiceException, NotFoundError, ValidationError
from ..data.repository import get_repository_manager
from ..external.plaid_client import get_plaid_client
from ..utils.validators import validate_user_exists
from ..config.logging import get_logger

logger = get_logger(__name__)

TRANSFER_FEE = Decimal("2.99")
SINGLE_TRANSFER_LIMIT = Decimal("25000")
DAILY_TRANSFER_LIMIT = Decimal("10000")
QUOTE_LIFETIME = timedelta(minutes=15)

# Plaid's transfer statuses, in this app's terms
PLAID_STATUS_MAP = {
    "pending": TransferStatus.PROCESSING,
    "posted": TransferStatus.IN_TRANSIT,
    "settled": TransferStatus.COMPLETED,
    "funds_available": TransferStatus.COMPLETED,
    "failed": TransferStatus.FAILED,
    "cancelled": TransferStatus.CANCELLED,
    "returned": TransferStatus.RETURNED,
}


def transfers_enabled() -> bool:
    return os.getenv("ENABLE_PLAID_TRANSFERS", "").lower() == "true"


class PlaidTransferService:
    """Service for managing money transfers via Plaid."""

    def __init__(self):
        self.repo = get_repository_manager()
        self.plaid_client = get_plaid_client()

    async def _get_owned_account(self, user_id: str, account_id: str):
        """The user's account and its active connection. Other users' accounts look like they don't exist."""
        account = await self.repo.get_plaid_account(account_id)
        connection = await self.repo.get_plaid_connection(account.connection_id) if account else None
        if not account or not connection or connection.user_id != user_id:
            raise NotFoundError("Bank account not found")
        if connection.status != PlaidConnectionStatus.ACTIVE:
            raise ValidationError("This bank connection needs attention. Please reconnect it.")
        return account, connection

    async def _get_owned_beneficiary(self, user_id: str, beneficiary_id: str):
        beneficiary = await self.repo.get_beneficiary_by_id(beneficiary_id)
        if not beneficiary or beneficiary.user_id != user_id:
            raise NotFoundError("Beneficiary not found")
        return beneficiary

    async def create_transfer_quote(self, user_id: str, request: TransferQuoteRequest) -> TransferQuote:
        """Price a transfer from one of the user's linked accounts."""
        logger.info(f"Creating transfer quote for user {user_id}")

        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        if request.source_currency != "USD":
            raise ValidationError("Only USD transfers are supported right now")
        if request.source_amount > SINGLE_TRANSFER_LIMIT:
            raise ValidationError(f"The most you can send at once is ${SINGLE_TRANSFER_LIMIT:,.0f}")

        account, _ = await self._get_owned_account(user_id, request.source_account_id)
        await self._get_owned_beneficiary(user_id, request.beneficiary_id)

        total_cost = request.source_amount + TRANSFER_FEE
        available = (account.balances or {}).get("available")
        if available is not None and Decimal(str(available)) < total_cost:
            raise ValidationError("Not enough money in this account to cover the transfer and fee")

        quote = TransferQuote(
            quote_id=str(uuid.uuid4()),
            user_id=user_id,
            from_amount=request.source_amount,
            from_currency=request.source_currency,
            to_amount=request.source_amount,
            to_currency=request.source_currency,
            exchange_rate=None,
            transfer_fee=TRANSFER_FEE,
            exchange_fee=Decimal("0.00"),
            total_fees=TRANSFER_FEE,
            total_cost=total_cost,
            expires_at=datetime.utcnow() + QUOTE_LIFETIME,
            transfer_type=TransferType.PLAID_TRANSFER,
        )

        await self.repo.create_quote_record({
            "quote_id": quote.quote_id,
            "user_id": user_id,
            "source_account_id": request.source_account_id,
            "beneficiary_id": request.beneficiary_id,
            "from_amount": quote.from_amount,
            "from_currency": quote.from_currency,
            "to_amount": quote.to_amount,
            "to_currency": quote.to_currency,
            "transfer_fee": quote.transfer_fee,
            "exchange_fee": quote.exchange_fee,
            "total_fees": quote.total_fees,
            "total_cost": quote.total_cost,
            "transfer_type": quote.transfer_type,
            "expires_at": quote.expires_at,
        })

        return quote

    async def initiate_transfer(
        self, user_id: str, quote_id: str, request: TransferInitiateRequest
    ) -> MoneyTransfer:
        """Debit the sender's account for an accepted quote."""
        logger.info(f"Initiating Plaid transfer for user {user_id} with quote {quote_id}")

        if not transfers_enabled():
            raise ValidationError("Bank transfers aren't available yet. No money was taken.")

        quote = await self.repo.get_quote_by_id(quote_id)
        if not quote or quote["user_id"] != user_id:
            raise NotFoundError("Quote not found or expired")
        if quote["expires_at"] < datetime.utcnow():
            raise ValidationError("This quote has expired. Please try again.")

        account, connection = await self._get_owned_account(user_id, quote["source_account_id"])
        beneficiary = await self._get_owned_beneficiary(user_id, quote["beneficiary_id"])

        used_today = await self.repo.get_user_transfer_volume(user_id, period="daily")
        if used_today + quote["from_amount"] > DAILY_TRANSFER_LIMIT:
            raise ValidationError(f"This would go over your daily limit of ${DAILY_TRANSFER_LIMIT:,.0f}")

        legal_name = await self.repo.get_user_legal_name(user_id)
        if not legal_name:
            raise ValidationError("Please add your name to your profile before sending money")

        # Claimed before calling Plaid, so a double tap or retry can't debit twice
        if not await self.repo.claim_quote(quote_id):
            raise ValidationError("This transfer has already been submitted")

        now = datetime.utcnow()
        transfer = MoneyTransfer(
            transfer_id=str(uuid.uuid4()),
            user_id=user_id,
            source_account_id=quote["source_account_id"],
            beneficiary_id=quote["beneficiary_id"],
            transfer_type=TransferType.PLAID_TRANSFER,
            status=TransferStatus.PENDING,
            priority=TransferPriority.STANDARD,
            source_amount=quote["from_amount"],
            source_currency=quote["from_currency"],
            destination_amount=quote["to_amount"],
            destination_currency=quote["to_currency"],
            transfer_fee=quote["transfer_fee"],
            exchange_fee=quote["exchange_fee"],
            total_fees=quote["total_fees"],
            total_cost=quote["total_cost"],
            purpose=request.purpose,
            reference=request.reference,
            recipient_message=request.recipient_message,
            quote_id=quote_id,
            created_at=now,
            updated_at=now,
            status_history=[{"status": TransferStatus.PENDING.value, "at": now.isoformat()}],
        )
        await self.repo.create_transfer(transfer)

        try:
            response = await self.plaid_client.create_transfer({
                "access_token": connection.access_token,
                "account_id": account.account_id,
                "amount": f"{quote['total_cost']:.2f}",
                "description": request.purpose[:15],
                "ach_class": "web",
                "user": {"legal_name": legal_name},
            })
        except Exception as e:
            logger.error(f"Plaid transfer failed for user {user_id}: {e}")
            self._set_status(transfer, TransferStatus.FAILED, reason=str(e))
            await self.repo.update_transfer(transfer)
            raise ExternalServiceException("Plaid", "create_transfer", str(e))

        transfer.external_reference = response["transfer_id"]
        transfer.processed_at = datetime.utcnow()
        self._set_status(transfer, TransferStatus.PROCESSING)
        await self.repo.update_transfer(transfer)

        logger.info(f"Initiated Plaid transfer {transfer.transfer_id} for user {user_id}")
        return transfer

    async def get_transfer_status(self, user_id: str, transfer_id: str) -> Dict[str, Any]:
        """A transfer's status, refreshed from Plaid."""
        transfer = await self._get_owned_transfer(user_id, transfer_id)

        if transfer.external_reference:
            try:
                remote = await self.plaid_client.get_transfer_status(transfer.external_reference)
            except Exception as e:
                logger.error(f"Failed to get transfer status for {transfer_id}: {e}")
                raise ExternalServiceException("Plaid", "get_transfer_status", str(e))

            new_status = PLAID_STATUS_MAP.get(remote["status"])
            if new_status and new_status != transfer.status:
                self._set_status(transfer, new_status, reason=remote.get("failure_reason"))
                if new_status == TransferStatus.COMPLETED:
                    transfer.completed_at = datetime.utcnow()
                await self.repo.update_transfer(transfer)

        return {
            "transfer_id": transfer.transfer_id,
            "status": transfer.status.value,
            "amount": str(transfer.source_amount),
            "currency": transfer.source_currency,
            "created_at": transfer.created_at.isoformat() if transfer.created_at else None,
            "completed_at": transfer.completed_at.isoformat() if transfer.completed_at else None,
            "failure_reason": transfer.failure_reason,
            "history": transfer.status_history,
        }

    async def cancel_transfer(self, user_id: str, transfer_id: str, reason: str = "User requested") -> MoneyTransfer:
        """Cancel with Plaid first, and only record it as cancelled if Plaid agrees."""
        transfer = await self._get_owned_transfer(user_id, transfer_id)
        if transfer.status in {
            TransferStatus.COMPLETED, TransferStatus.FAILED, TransferStatus.CANCELLED, TransferStatus.RETURNED
        }:
            raise ValidationError("This transfer can no longer be cancelled")

        if transfer.external_reference:
            try:
                await self.plaid_client.cancel_transfer(transfer.external_reference)
            except Exception as e:
                logger.error(f"Failed to cancel transfer {transfer_id}: {e}")
                raise ExternalServiceException("Plaid", "cancel_transfer", str(e))

        self._set_status(transfer, TransferStatus.CANCELLED, reason=reason)
        await self.repo.update_transfer(transfer)
        return transfer

    async def list_user_transfers(self, user_id: str, limit: int = 50, offset: int = 0) -> List[MoneyTransfer]:
        transfers = await self.repo.get_user_transfers(user_id)
        return transfers[offset:offset + limit]

    async def _get_owned_transfer(self, user_id: str, transfer_id: str) -> MoneyTransfer:
        transfer = await self.repo.get_transfer_by_id(transfer_id)
        if not transfer or transfer.user_id != user_id:
            raise NotFoundError("Transfer not found")
        return transfer

    @staticmethod
    def _set_status(transfer: MoneyTransfer, status: TransferStatus, reason: str = None) -> None:
        now = datetime.utcnow()
        transfer.status = status
        transfer.updated_at = now
        entry = {"status": status.value, "at": now.isoformat()}
        if reason:
            entry["reason"] = reason
            transfer.failure_reason = reason
        transfer.status_history = [*transfer.status_history, entry]


# Dependency provider
def get_plaid_transfer_service() -> PlaidTransferService:
    """Dependency provider for Plaid transfer service."""
    return PlaidTransferService()
