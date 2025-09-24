"""
Mastercard API endpoints for payment processing.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from decimal import Decimal

from app.database.config import get_db
from app.services.mastercard_service import get_mastercard_service, MastercardService
from app.core.exceptions import ValidationException, NotFoundError, BusinessLogicError

router = APIRouter(prefix="/mastercard", tags=["Mastercard"])
security = HTTPBearer()


# Request/Response Models
class PaymentRequest(BaseModel):
    amount: Decimal = Field(..., description="Payment amount")
    currency: str = Field(default="USD", description="Currency code")
    payment_method: Dict[str, Any] = Field(..., description="Payment method details")
    description: Optional[str] = Field(None, description="Payment description")
    reference: Optional[str] = Field(None, description="Payment reference")


class CardValidationRequest(BaseModel):
    card_number: str = Field(..., description="Card number")
    expiry_month: str = Field(..., description="Expiry month")
    expiry_year: str = Field(..., description="Expiry year")
    cvv: str = Field(..., description="CVV code")


class CardTokenizationRequest(BaseModel):
    card_number: str = Field(..., description="Card number")
    expiry_month: str = Field(..., description="Expiry month")
    expiry_year: str = Field(..., description="Expiry year")
    cardholder_name: str = Field(..., description="Cardholder name")


class TransferRequest(BaseModel):
    amount: Decimal = Field(..., description="Transfer amount")
    currency: str = Field(default="USD", description="Currency code")
    sender: Dict[str, Any] = Field(..., description="Sender details")
    recipient: Dict[str, Any] = Field(..., description="Recipient details")
    purpose: Optional[str] = Field(None, description="Transfer purpose")
    reference: Optional[str] = Field(None, description="Transfer reference")


class RefundRequest(BaseModel):
    amount: Decimal = Field(..., description="Refund amount")
    currency: str = Field(default="USD", description="Currency code")
    reason: Optional[str] = Field(None, description="Refund reason")


# API Endpoints
@router.post("/payments")
async def create_payment(
    request: PaymentRequest,
    credentials: HTTPBearer = Depends(security),
    db: Session = Depends(get_db),
    mastercard_service: MastercardService = Depends(get_mastercard_service)
):
    """Create a new payment using Mastercard API."""
    try:
        token = credentials.credentials
        payment_data = request.dict()
        
        result = await mastercard_service.process_payment(token, payment_data, db)
        
        return {
            "success": True,
            "data": result,
            "message": "Payment processed successfully"
        }
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment processing failed: {str(e)}"
        )


@router.get("/payments/{payment_id}")
async def get_payment_status(
    payment_id: str,
    credentials: HTTPBearer = Depends(security),
    db: Session = Depends(get_db),
    mastercard_service: MastercardService = Depends(get_mastercard_service)
):
    """Get payment status by ID."""
    try:
        token = credentials.credentials
        result = await mastercard_service.get_payment_status(token, payment_id, db)
        
        return {
            "success": True,
            "data": result,
            "message": "Payment status retrieved successfully"
        }
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get payment status: {str(e)}"
        )


@router.post("/payments/{payment_id}/refund")
async def refund_payment(
    payment_id: str,
    request: RefundRequest,
    credentials: HTTPBearer = Depends(security),
    db: Session = Depends(get_db),
    mastercard_service: MastercardService = Depends(get_mastercard_service)
):
    """Refund a payment."""
    try:
        token = credentials.credentials
        refund_data = request.dict()
        
        result = await mastercard_service.refund_payment(token, payment_id, refund_data, db)
        
        return {
            "success": True,
            "data": result,
            "message": "Payment refunded successfully"
        }
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Refund processing failed: {str(e)}"
        )


@router.post("/cards/validate")
async def validate_card(
    request: CardValidationRequest,
    credentials: HTTPBearer = Depends(security),
    db: Session = Depends(get_db),
    mastercard_service: MastercardService = Depends(get_mastercard_service)
):
    """Validate card information."""
    try:
        token = credentials.credentials
        card_data = request.dict()
        
        result = await mastercard_service.validate_card(token, card_data, db)
        
        return {
            "success": True,
            "data": result,
            "message": "Card validated successfully"
        }
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Card validation failed: {str(e)}"
        )


@router.post("/cards/tokenize")
async def tokenize_card(
    request: CardTokenizationRequest,
    credentials: HTTPBearer = Depends(security),
    db: Session = Depends(get_db),
    mastercard_service: MastercardService = Depends(get_mastercard_service)
):
    """Tokenize card for secure storage."""
    try:
        token = credentials.credentials
        card_data = request.dict()
        
        result = await mastercard_service.tokenize_card(token, card_data, db)
        
        return {
            "success": True,
            "data": result,
            "message": "Card tokenized successfully"
        }
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Card tokenization failed: {str(e)}"
        )


@router.post("/transfers")
async def create_transfer(
    request: TransferRequest,
    credentials: HTTPBearer = Depends(security),
    db: Session = Depends(get_db),
    mastercard_service: MastercardService = Depends(get_mastercard_service)
):
    """Create a money transfer."""
    try:
        token = credentials.credentials
        transfer_data = request.dict()
        
        result = await mastercard_service.create_transfer(token, transfer_data, db)
        
        return {
            "success": True,
            "data": result,
            "message": "Transfer created successfully"
        }
        
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transfer creation failed: {str(e)}"
        )


@router.get("/transfers/{transfer_id}")
async def get_transfer_status(
    transfer_id: str,
    credentials: HTTPBearer = Depends(security),
    db: Session = Depends(get_db),
    mastercard_service: MastercardService = Depends(get_mastercard_service)
):
    """Get transfer status by ID."""
    try:
        token = credentials.credentials
        result = await mastercard_service.get_transfer_status(token, transfer_id, db)
        
        return {
            "success": True,
            "data": result,
            "message": "Transfer status retrieved successfully"
        }
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get transfer status: {str(e)}"
        )


@router.get("/exchange-rates")
async def get_exchange_rates(
    base_currency: str = "USD",
    credentials: HTTPBearer = Depends(security),
    db: Session = Depends(get_db),
    mastercard_service: MastercardService = Depends(get_mastercard_service)
):
    """Get current exchange rates."""
    try:
        token = credentials.credentials
        result = await mastercard_service.get_exchange_rates(token, base_currency, db)
        
        return {
            "success": True,
            "data": result,
            "message": "Exchange rates retrieved successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get exchange rates: {str(e)}"
        )


@router.get("/transactions")
async def get_transaction_history(
    limit: int = 100,
    credentials: HTTPBearer = Depends(security),
    db: Session = Depends(get_db),
    mastercard_service: MastercardService = Depends(get_mastercard_service)
):
    """Get transaction history."""
    try:
        token = credentials.credentials
        result = await mastercard_service.get_transaction_history(token, limit=limit, db=db)
        
        return {
            "success": True,
            "data": result,
            "message": "Transaction history retrieved successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get transaction history: {str(e)}"
        )
