"""
Money transfer service for the fintech backend.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any

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
from ..utils.validators import validate_user_exists
from ..config.logging import get_logger
from ..external.payment_gateway import get_payment_gateway
from .plaid_transfer_service import get_plaid_transfer_service, PlaidTransferService

logger = get_logger(__name__)


class MoneyTransferService:
    """Service for external money transfers and beneficiary management."""

    def __init__(self):
        self.repo = get_repository_manager()
        self.payment_gateway = get_payment_gateway()
        self.plaid_transfer_service = get_plaid_transfer_service()

    # Beneficiaries
    async def list_beneficiaries(self, user_id: str) -> Dict[str, Any]:
        if not await validate_user_exists(user_id, self.repo):
            raise NotFoundError(f"User {user_id} not found")
        beneficiaries = await self.repo.get_user_beneficiaries(user_id)
        masked = [self._masked(b) for b in beneficiaries]
        return {
            "beneficiaries": masked,
            "total_count": len(masked),
            "favorites": [b for b in masked if b.is_favorite],
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
            status=BeneficiaryStatus.ACTIVE,
            nickname=req.nickname,
            relationship=req.relationship,
            notes=req.notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        await self.repo.create_beneficiary(beneficiary)
        return self._masked(beneficiary)

    async def update_beneficiary(self, user_id: str, beneficiary_id: str, req: BeneficiaryUpdateRequest) -> Beneficiary:
        beneficiary = await self._get_user_beneficiary(user_id, beneficiary_id)
        for field, value in req.dict(exclude_unset=True).items():
            setattr(beneficiary, field, value)
        beneficiary.updated_at = datetime.utcnow()
        await self.repo.update_beneficiary(beneficiary)
        return self._masked(beneficiary)

    async def delete_beneficiary(self, user_id: str, beneficiary_id: str) -> bool:
        beneficiary = await self._get_user_beneficiary(user_id, beneficiary_id)
        await self.repo.delete_beneficiary(beneficiary.beneficiary_id)
        return True

    # Quotes and rates
    async def get_transfer_quote(self, user_id: str, req: TransferQuoteRequest) -> Dict[str, Any]:
        # Plaid is the only way money can leave a user's account in this app
        if req.transfer_type != TransferType.PLAID_TRANSFER:
            raise ValidationError("This type of transfer isn't available yet")
        quote = await self.plaid_transfer_service.create_transfer_quote(user_id, req)
        return {"quote": quote, "alternative_quotes": []}

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
        return await self.plaid_transfer_service.initiate_transfer(user_id, quote_id, req)

    async def cancel_transfer(self, user_id: str, transfer_id: str, req: TransferCancelRequest) -> MoneyTransfer:
        return await self.plaid_transfer_service.cancel_transfer(user_id, transfer_id, req.reason)

    async def track_transfer(self, user_id: str, transfer_id: str) -> Dict[str, Any]:
        return await self.plaid_transfer_service.get_transfer_status(user_id, transfer_id)

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
            TransferType.PLAID_TRANSFER: Decimal("2.99"),
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

    @staticmethod
    def _masked(beneficiary: Beneficiary) -> Beneficiary:
        """Beneficiary details for API responses: account numbers show the last four digits only."""
        def last_four(value: Optional[str]) -> Optional[str]:
            return f"****{value[-4:]}" if value else value

        return beneficiary.model_copy(update={
            "account_number": last_four(beneficiary.account_number),
            "iban": last_four(beneficiary.iban),
            "mobile_money_number": last_four(beneficiary.mobile_money_number),
        })


# Dependency provider

def get_money_transfer_service() -> MoneyTransferService:
    return MoneyTransferService()
