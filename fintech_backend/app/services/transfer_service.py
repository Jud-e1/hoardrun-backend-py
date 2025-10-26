"""
Money transfer service for the fintech backend.
"""

import uuid
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import asyncio

from ..models.transfer import (
    Beneficiary, BeneficiaryCreateRequest, BeneficiaryUpdateRequest,
    BeneficiaryStatus, TransferType, TransferStatus, TransferPriority,
    TransferQuoteRequest, TransferInitiateRequest, TransferCancelRequest,
    TransferQuote, MoneyTransfer, ExchangeRate, TransferFeesResponse,
    TransferLimitsResponse, ExchangeRateResponse, CountryCorridor
)
from ..core.exceptions import (
    ValidationError, NotFoundError, BusinessLogicError, UnauthorizedError
)
from ..data.repository import get_repository_manager
from ..utils.validators import validate_user_exists, validate_account_exists
from ..utils.calculations import calculate_fee
from ..config.logging import get_logger
from ..external.bank_api import get_bank_api_client
from ..external.mobile_money import MockMobileMoneyClient, MobileMoneyProvider
from ..external.payment_gateway import get_payment_gateway
from .plaid_transfer_service import get_plaid_transfer_service, PlaidTransferService

logger = get_logger(__name__)


class MoneyTransferService:
    """Service for external money transfers and beneficiary management."""

    def __init__(self):
        self.repo = get_repository_manager()
        self.bank_api = get_bank_api_client()
        self.payment_gateway = get_payment_gateway()
        self.mobile_money = MockMobileMoneyClient()
        self.plaid_transfer_service = get_plaid_transfer_service()

    # Beneficiaries
    async def list_beneficiaries(self, user_id: str) -> Dict[str, Any]:
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        beneficiaries = await self.repo.get_user_beneficiaries(user_id)
        favorites = [b for b in beneficiaries if b.is_favorite]
        return {
            "beneficiaries": beneficiaries,
            "total_count": len(beneficiaries),
            "favorites": favorites,
        }

    async def create_beneficiary(self, user_id: str, req: BeneficiaryCreateRequest) -> Beneficiary:
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        beneficiary = Beneficiary(
            beneficiary_id=str(uuid.uuid4()),
            user_id=user_id,
            beneficiary_type=req.beneficiary_type,
            first_name=req.first_name,
            last_name=req.last_name,
            business_name=req.business_name,
            email=req.email,
            phone_number=req.phone_number,
            address_line1=req.address_line1,
            address_line2=req.address_line2,
            city=req.city,
            state_province=req.state_province,
            postal_code=req.postal_code,
            country=req.country,
            bank_name=req.bank_name,
            bank_code=req.bank_code,
            swift_bic=req.swift_bic,
            account_number=req.account_number,
            iban=req.iban,
            mobile_money_provider=req.mobile_money_provider,
            mobile_money_number=req.mobile_money_number,
            status=BeneficiaryStatus.PENDING_VERIFICATION,
            nickname=req.nickname,
            relationship=req.relationship,
            notes=req.notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        await self.repo.create_beneficiary(beneficiary)
        # Simulate verification
        await asyncio.sleep(0.05)
        beneficiary.status = BeneficiaryStatus.VERIFIED
        beneficiary.verification_date = datetime.utcnow()
        await self.repo.update_beneficiary(beneficiary)
        return beneficiary

    async def update_beneficiary(self, user_id: str, beneficiary_id: str, req: BeneficiaryUpdateRequest) -> Beneficiary:
        beneficiary = await self._get_user_beneficiary(user_id, beneficiary_id)
        for field, value in req.dict(exclude_unset=True).items():
            setattr(beneficiary, field, value)
        beneficiary.updated_at = datetime.utcnow()
        await self.repo.update_beneficiary(beneficiary)
        return beneficiary

    async def delete_beneficiary(self, user_id: str, beneficiary_id: str) -> bool:
        beneficiary = await self._get_user_beneficiary(user_id, beneficiary_id)
        await self.repo.delete_beneficiary(beneficiary.beneficiary_id)
        return True

    # Quotes and rates
    async def get_transfer_quote(self, user_id: str, req: TransferQuoteRequest) -> Dict[str, Any]:
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        if not await validate_account_exists(req.source_account_id, self.repo):
            raise NotFoundError("Source account not found")
        account = await self.repo.get_account_by_id(req.source_account_id)
        if account.user_id != user_id:
            raise UnauthorizedError("You don't have access to this account")

        # Check if this is a Plaid transfer
        if req.transfer_type == TransferType.PLAID_TRANSFER:
            return await self.plaid_transfer_service.get_transfer_quote(user_id, req)

        # Get bank rates (mock) and compose ExchangeRate
        rate_value = await self._get_mock_rate(req.source_currency, req.destination_currency)
        exchange_fee = (req.source_amount * Decimal("0.005")).quantize(Decimal("0.01"))  # 0.5%
        transfer_fee = self._estimate_transfer_fee(req.transfer_type, req.priority, req.source_amount)
        total_fees = (exchange_fee + transfer_fee).quantize(Decimal("0.01"))
        to_amount = (req.source_amount * rate_value - exchange_fee).quantize(Decimal("0.01"))

        exchange_rate = ExchangeRate(
            from_currency=req.source_currency,
            to_currency=req.destination_currency,
            rate=rate_value,
            inverse_rate=(Decimal("1.0") / rate_value).quantize(Decimal("0.0001")),
            margin=Decimal("0.02"),
            valid_until=datetime.utcnow() + timedelta(minutes=10)
        )
        quote = TransferQuote(
            quote_id=str(uuid.uuid4()),
            from_amount=req.source_amount,
            from_currency=req.source_currency,
            to_amount=to_amount,
            to_currency=req.destination_currency,
            exchange_rate=exchange_rate,
            transfer_fee=transfer_fee,
            exchange_fee=exchange_fee,
            total_fees=total_fees,
            total_cost=(req.source_amount + total_fees).quantize(Decimal("0.01")),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            transfer_type=req.transfer_type,
        )
        # Alternative quotes (different priority)
        alternatives = [
            self._alternative_quote(quote, TransferPriority.EXPRESS),
            self._alternative_quote(quote, TransferPriority.URGENT),
        ]
        return {"quote": quote, "alternative_quotes": alternatives}

    async def get_exchange_rates(self, base_currency: str, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        # Use payment gateway mock exchange rates if available
        rates = await self.payment_gateway.get_exchange_rates(base_currency)
        now = datetime.utcnow()
        result = []
        for code, rate in rates.items():
            if symbols and code not in symbols:
                continue
            result.append(ExchangeRate(
                from_currency=base_currency,
                to_currency=code,
                rate=Decimal(str(rate)),
                inverse_rate=(Decimal("1.0") / Decimal(str(rate))).quantize(Decimal("0.0001")),
                margin=Decimal("0.02"),
                valid_until=now + timedelta(minutes=15)
            ))
        return {"rates": result, "base_currency": base_currency, "last_updated": now}

    # Transfers
    async def initiate_transfer(self, user_id: str, quote_id: str, req: TransferInitiateRequest) -> MoneyTransfer:
        quote = await self.repo.get_quote_by_id(quote_id)
        if not quote:
            raise NotFoundError("Quote not found or expired")
        if quote.expires_at < datetime.utcnow():
            raise BusinessLogicError("Quote has expired")

        # Check if this is a Plaid transfer
        if hasattr(quote, "transfer_type") and quote.transfer_type == TransferType.PLAID_TRANSFER:
            return await self.plaid_transfer_service.initiate_transfer(user_id, quote_id, req)

        # Validate user & account
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")

        # Verify beneficiary and account
        beneficiary = await self._get_user_beneficiary(user_id, quote.get("beneficiary_id", "")) if isinstance(quote, dict) else None
        source_account_id = quote.get("source_account_id") if isinstance(quote, dict) else None
        if not beneficiary or not source_account_id:
            # In our mock, store quote context in repo or embed in quote dict; fallback to request context
            pass

        # For mock path, retrieve a stored context or simulate minimal checks
        transfer = MoneyTransfer(
            transfer_id=str(uuid.uuid4()),
            user_id=user_id,
            source_account_id=quote.get("source_account_id") if isinstance(quote, dict) else "",
            beneficiary_id=quote.get("beneficiary_id") if isinstance(quote, dict) else "",
            transfer_type=quote.transfer_type if hasattr(quote, "transfer_type") else TransferType.DOMESTIC_BANK,
            status=TransferStatus.PROCESSING,
            priority=TransferPriority.STANDARD,
            source_amount=quote.from_amount if hasattr(quote, "from_amount") else Decimal("0"),
            source_currency=quote.from_currency if hasattr(quote, "from_currency") else "USD",
            destination_amount=quote.to_amount if hasattr(quote, "to_amount") else Decimal("0"),
            destination_currency=quote.to_currency if hasattr(quote, "to_currency") else "USD",
            exchange_rate_used=quote.exchange_rate.rate if hasattr(quote, "exchange_rate") and quote.exchange_rate else None,
            transfer_fee=quote.transfer_fee if hasattr(quote, "transfer_fee") else Decimal("0"),
            exchange_fee=quote.exchange_fee if hasattr(quote, "exchange_fee") else Decimal("0"),
            total_fees=quote.total_fees if hasattr(quote, "total_fees") else Decimal("0"),
            total_cost=quote.total_cost if hasattr(quote, "total_cost") else Decimal("0"),
            purpose=req.purpose,
            reference=req.reference,
            recipient_message=req.recipient_message,
            quote_id=quote_id,
            external_reference=f"EXT{random.randint(100000,999999)}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            status_history=[{"status": "processing", "at": datetime.utcnow().isoformat()}],
            compliance_check_passed=True,
            requires_documents=False,
        )
        await self.repo.create_transfer(transfer)

        # Simulate processing path depending on transfer type
        await asyncio.sleep(0.2)
        transfer.status = TransferStatus.IN_TRANSIT
        transfer.status_history.append({"status": "in_transit", "at": datetime.utcnow().isoformat()})
        transfer.processed_at = datetime.utcnow()
        transfer.estimated_arrival = datetime.utcnow() + timedelta(hours=12)
        await self.repo.update_transfer(transfer)

        # Simulate completion later
        asyncio.create_task(self._complete_transfer_async(transfer.transfer_id))
        return transfer

    async def cancel_transfer(self, user_id: str, transfer_id: str, req: TransferCancelRequest) -> MoneyTransfer:
        transfer = await self._get_user_transfer(user_id, transfer_id)
        if transfer.status in [TransferStatus.COMPLETED, TransferStatus.FAILED, TransferStatus.CANCELLED]:
            raise BusinessLogicError("Transfer can no longer be cancelled")

        # Check if this is a Plaid transfer
        if transfer.transfer_type == TransferType.PLAID_TRANSFER:
            return await self.plaid_transfer_service.cancel_transfer(user_id, transfer_id, req)

        transfer.status = TransferStatus.CANCELLED
        transfer.status_history.append({"status": "cancelled", "reason": req.reason, "at": datetime.utcnow().isoformat()})
        transfer.updated_at = datetime.utcnow()
        await self.repo.update_transfer(transfer)
        return transfer

    async def track_transfer(self, user_id: str, transfer_id: str) -> Dict[str, Any]:
        transfer = await self._get_user_transfer(user_id, transfer_id)

        # Check if this is a Plaid transfer
        if transfer.transfer_type == TransferType.PLAID_TRANSFER:
            return await self.plaid_transfer_service.track_transfer(user_id, transfer_id)

        return {
            "transfer": transfer,
            "tracking_events": transfer.status_history,
            "estimated_completion": transfer.estimated_arrival,
            "next_update": datetime.utcnow() + timedelta(minutes=15)
        }

    async def list_transfers(self, user_id: str, status: Optional[TransferStatus] = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        transfers = await self.repo.get_user_transfers(user_id)
        if status:
            transfers = [t for t in transfers if t.status == status]
        total = len(transfers)
        page = transfers[offset:offset+limit]
        pending = len([t for t in transfers if t.status in {TransferStatus.PENDING, TransferStatus.PROCESSING, TransferStatus.IN_TRANSIT}])
        return {"transfers": page, "total_count": total, "pending_count": pending}

    # Limits, fees, corridors
    async def get_transfer_limits(self, user_id: str) -> Dict[str, Any]:
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        daily = Decimal("10000")
        monthly = Decimal("50000")
        annual = Decimal("300000")
        used_daily = await self.repo.get_user_transfer_volume(user_id, period="daily")
        used_monthly = await self.repo.get_user_transfer_volume(user_id, period="monthly")
        used_annual = await self.repo.get_user_transfer_volume(user_id, period="annual")
        return {
            "daily_limit": daily,
            "monthly_limit": monthly,
            "annual_limit": annual,
            "daily_used": used_daily,
            "monthly_used": used_monthly,
            "annual_used": used_annual,
            "remaining_daily": max(Decimal("0"), daily - used_daily),
            "remaining_monthly": max(Decimal("0"), monthly - used_monthly),
            "remaining_annual": max(Decimal("0"), annual - used_annual),
            "single_transfer_limit": Decimal("25000"),
        }

    async def get_fee_schedule(self, transfer_type: TransferType) -> Dict[str, Any]:
        base_fee = {
            TransferType.DOMESTIC_BANK: Decimal("1.00"),
            TransferType.INTERNATIONAL_WIRE: Decimal("8.50"),
            TransferType.MOBILE_MONEY: Decimal("0.75"),
            TransferType.INSTANT_TRANSFER: Decimal("1.50"),
            TransferType.REMITTANCE: Decimal("6.00"),
            TransferType.CRYPTO: Decimal("3.00"),
        }[transfer_type]
        variable = Decimal("0.003")  # 0.3%
        priority_fees = {
            "standard": Decimal("0.00"),
            "express": Decimal("2.00"),
            "urgent": Decimal("5.00"),
        }
        currency_pairs = [
            {"from": "USD", "to": "EUR", "variable": variable},
            {"from": "USD", "to": "GBP", "variable": variable},
            {"from": "EUR", "to": "USD", "variable": variable},
        ]
        return {
            "transfer_type": transfer_type,
            "fee_structure": {"base": base_fee, "variable": variable},
            "currency_pairs": currency_pairs,
            "priority_fees": {k: v for k, v in priority_fees.items()}
        }

    async def get_transfer_corridors(self) -> Dict[str, Any]:
        corridors = [
            CountryCorridor(from_country="US", to_country="GB", supported_transfer_types=[TransferType.DOMESTIC_BANK, TransferType.INTERNATIONAL_WIRE], average_delivery_time="1-2 business days", compliance_level="standard"),
            CountryCorridor(from_country="US", to_country="NG", supported_transfer_types=[TransferType.MOBILE_MONEY, TransferType.REMITTANCE], average_delivery_time="minutes to hours", compliance_level="enhanced"),
            CountryCorridor(from_country="GB", to_country="EU", supported_transfer_types=[TransferType.INTERNATIONAL_WIRE], average_delivery_time="same-day", compliance_level="standard"),
        ]
        return {
            "corridors": corridors,
            "total_countries": 15,
            "popular_corridors": corridors[:2]
        }

    # Helpers
    async def _get_user_beneficiary(self, user_id: str, beneficiary_id: str) -> Beneficiary:
        beneficiary = await self.repo.get_beneficiary_by_id(beneficiary_id)
        if not beneficiary:
            raise NotFoundError("Beneficiary not found")
        if beneficiary.user_id != user_id:
            raise UnauthorizedError("You don't have access to this beneficiary")
        return beneficiary

    async def _get_user_transfer(self, user_id: str, transfer_id: str) -> MoneyTransfer:
        transfer = await self.repo.get_transfer_by_id(transfer_id)
        if not transfer:
            raise NotFoundError("Transfer not found")
        if transfer.user_id != user_id:
            raise UnauthorizedError("You don't have access to this transfer")
        return transfer

    def _estimate_transfer_fee(self, transfer_type: TransferType, priority: TransferPriority, amount: Decimal) -> Decimal:
        schedule = {
            TransferType.DOMESTIC_BANK: (Decimal("1.00"), Decimal("0.002")),
            TransferType.INTERNATIONAL_WIRE: (Decimal("10.00"), Decimal("0.005")),
            TransferType.MOBILE_MONEY: (Decimal("0.50"), Decimal("0.004")),
            TransferType.INSTANT_TRANSFER: (Decimal("1.50"), Decimal("0.003")),
            TransferType.REMITTANCE: (Decimal("5.00"), Decimal("0.004")),
            TransferType.CRYPTO: (Decimal("2.50"), Decimal("0.003")),
            TransferType.PLAID_TRANSFER: (Decimal("0.00"), Decimal("0.000")),  # No fees for Plaid transfers
        }[transfer_type]
        base, variable = schedule
        fee = base + (amount * variable)
        if priority == TransferPriority.EXPRESS:
            fee += Decimal("2.00")
        elif priority == TransferPriority.URGENT:
            fee += Decimal("5.00")
        return fee.quantize(Decimal("0.01"))

    async def _get_mock_rate(self, from_curr: str, to_curr: str) -> Decimal:
        if from_curr == to_curr:
            return Decimal("1.0")
        # Use payment gateway exchange rates
        rates = await self.payment_gateway.get_exchange_rates(from_curr)
        rate = rates.get(to_curr)
        if rate is None:
            # fallback mock
            rate = 0.9 if to_curr in ("EUR", "GBP") else 1.1
        return Decimal(str(rate)).quantize(Decimal("0.0001"))

    def _alternative_quote(self, quote: TransferQuote, priority: TransferPriority) -> TransferQuote:
        factor = Decimal("1.00")
        if priority == TransferPriority.EXPRESS:
            factor = Decimal("0.995")
        elif priority == TransferPriority.URGENT:
            factor = Decimal("0.992")
        alt_transfer_fee = (quote.transfer_fee + (Decimal("2.00") if priority == TransferPriority.EXPRESS else Decimal("5.00") if priority == TransferPriority.URGENT else Decimal("0"))).quantize(Decimal("0.01"))
        alt_total_fees = (alt_transfer_fee + quote.exchange_fee).quantize(Decimal("0.01"))
        alt_to_amount = (quote.to_amount * factor).quantize(Decimal("0.01"))
        return TransferQuote(
            quote_id=str(uuid.uuid4()),
            from_amount=quote.from_amount,
            from_currency=quote.from_currency,
            to_amount=alt_to_amount,
            to_currency=quote.to_currency,
            exchange_rate=quote.exchange_rate,
            transfer_fee=alt_transfer_fee,
            exchange_fee=quote.exchange_fee,
            total_fees=alt_total_fees,
            total_cost=(quote.from_amount + alt_total_fees).quantize(Decimal("0.01")),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            transfer_type=quote.transfer_type,
        )

    async def _complete_transfer_async(self, transfer_id: str):
        try:
            await asyncio.sleep(1.0)  # simulate network settlement
            transfer = await self.repo.get_transfer_by_id(transfer_id)
            if not transfer or transfer.status in [TransferStatus.CANCELLED, TransferStatus.FAILED, TransferStatus.COMPLETED]:
                return
            transfer.status = TransferStatus.COMPLETED
            transfer.status_history.append({"status": "completed", "at": datetime.utcnow().isoformat()})
            transfer.completed_at = datetime.utcnow()
            await self.repo.update_transfer(transfer)
            logger.info(f"Transfer {transfer_id} completed")
        except Exception as e:
            logger.error(f"Failed completing transfer {transfer_id}: {e}")


# Dependency provider

def get_money_transfer_service() -> MoneyTransferService:
    return MoneyTransferService()

