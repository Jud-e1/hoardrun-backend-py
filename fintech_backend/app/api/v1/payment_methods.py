"""
Payment Methods API Routes
Handles payment method management including bank accounts, cards, mobile money, digital wallets, etc.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer

from ...core.auth import get_current_user
from ...models.payment_methods import (
    PaymentMethodCreateRequest,
    PaymentMethodUpdateRequest,
    PaymentMethodProfile,
    PaymentMethodVerificationRequest,
    PaymentMethodVerificationResponse,
    PaymentMethodType,
    PaymentMethodStatus,
    PaymentMethodListResponse,
    PaymentMethodResponse
)
from ...models.base import BaseResponse, PaginatedResponse
from ...services.payment_methods_service import PaymentMethodsService
from ...core.exceptions import ValidationError, NotFoundError, ConflictError

router = APIRouter(prefix="/payment-methods", tags=["Payment Methods"])
security = HTTPBearer()

# Initialize service
payment_methods_service = PaymentMethodsService()

@router.get(
    "",
    response_model=PaginatedResponse[PaymentMethodProfile],
    summary="Get Payment Methods",
    description="Retrieve user's payment methods with filtering and pagination"
)
async def get_payment_methods(
    current_user: dict = Depends(get_current_user),
    payment_type: Optional[PaymentMethodType] = Query(None, description="Filter by payment method type"),
    status: Optional[PaymentMethodStatus] = Query(None, description="Filter by status"),
    is_default: Optional[bool] = Query(None, description="Filter by default status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page")
):
    """
    Get user's payment methods with optional filtering.
    
    Supports filtering by:
    - Payment method type (bank_account, credit_card, etc.)
    - Status (active, inactive, pending_verification, etc.)
    - Default payment method flag
    """
    try:
        result = await payment_methods_service.get_user_payment_methods(
            user_id=current_user["user_id"],
            payment_type=payment_type,
            status=status,
            is_default=is_default,
            page=page,
            limit=limit
        )
        
        return PaginatedResponse(
            success=True,
            message="Payment methods retrieved successfully",
            data=result["items"],
            total=result["total"],
            page=page,
            limit=limit,
            total_pages=result["total_pages"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment methods: {str(e)}"
        )

@router.post(
    "",
    response_model=PaymentMethodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Payment Method",
    description="Add a new payment method for the user"
)
async def add_payment_method(
    payment_method_data: PaymentMethodCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Add a new payment method.
    
    Supports various payment method types:
    - Bank accounts (with account number, routing number, etc.)
    - Credit/Debit cards (with card number, expiry, CVV)
    - Mobile money accounts (with phone number, provider)
    - Digital wallets (PayPal, Stripe, etc.)
    - Crypto wallets (with wallet address)
    """
    try:
        # Check if user has reached payment method limit
        existing_count = await payment_methods_service.get_user_payment_methods_count(
            user_id=current_user["user_id"]
        )
        
        if existing_count >= 10:  # Maximum 10 payment methods per user
            raise ConflictError("Maximum number of payment methods reached (10)")
        
        # Add the payment method
        payment_method = await payment_methods_service.add_payment_method(
            user_id=current_user["user_id"],
            payment_method_data=payment_method_data
        )
        
        return PaymentMethodResponse(
            success=True,
            message="Payment method added successfully",
            data={"payment_method": payment_method}
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add payment method: {str(e)}"
        )

@router.put(
    "/{payment_method_id}",
    response_model=PaymentMethodResponse,
    summary="Update Payment Method",
    description="Update an existing payment method"
)
async def update_payment_method(
    payment_method_id: str,
    payment_method_data: PaymentMethodUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update an existing payment method.
    
    Allows updating:
    - Display name/nickname
    - Default status
    - Billing address
    - Some non-sensitive details
    
    Note: Sensitive information like card numbers cannot be updated for security reasons.
    """
    try:
        # Verify payment method belongs to user
        existing_method = await payment_methods_service.get_payment_method_by_id(
            payment_method_id=payment_method_id,
            user_id=current_user["user_id"]
        )
        
        if not existing_method:
            raise NotFoundError("Payment method not found")
        
        # Update the payment method
        updated_method = await payment_methods_service.update_payment_method(
            payment_method_id=payment_method_id,
            user_id=current_user["user_id"],
            payment_method_data=payment_method_data
        )
        
        return PaymentMethodResponse(
            success=True,
            message="Payment method updated successfully",
            data={"payment_method": updated_method}
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update payment method: {str(e)}"
        )

@router.delete(
    "/{payment_method_id}",
    response_model=BaseResponse,
    summary="Remove Payment Method",
    description="Remove a payment method from user's account"
)
async def remove_payment_method(
    payment_method_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Remove a payment method from user's account.
    
    Notes:
    - Cannot remove the default payment method if it's the only one
    - Will check for pending transactions before removal
    - Soft delete for audit purposes
    """
    try:
        # Verify payment method belongs to user
        existing_method = await payment_methods_service.get_payment_method_by_id(
            payment_method_id=payment_method_id,
            user_id=current_user["user_id"]
        )
        
        if not existing_method:
            raise NotFoundError("Payment method not found")
        
        # Check if it's the only payment method and is default
        user_methods_count = await payment_methods_service.get_user_payment_methods_count(
            user_id=current_user["user_id"]
        )
        
        if user_methods_count == 1 and existing_method.is_default:
            raise ConflictError("Cannot remove the only default payment method")
        
        # Check for pending transactions
        has_pending = await payment_methods_service.has_pending_transactions(
            payment_method_id=payment_method_id
        )
        
        if has_pending:
            raise ConflictError("Cannot remove payment method with pending transactions")
        
        # Remove the payment method
        await payment_methods_service.remove_payment_method(
            payment_method_id=payment_method_id,
            user_id=current_user["user_id"]
        )
        
        return BaseResponse(
            success=True,
            message="Payment method removed successfully",
            data={"payment_method_id": payment_method_id}
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove payment method: {str(e)}"
        )

@router.post(
    "/{payment_method_id}/verify",
    response_model=BaseResponse,
    summary="Verify Payment Method",
    description="Initiate or complete payment method verification"
)
async def verify_payment_method(
    payment_method_id: str,
    verification_data: PaymentMethodVerificationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Verify a payment method.
    
    Verification methods vary by payment type:
    - Bank accounts: Micro-deposits or instant verification
    - Cards: Small authorization charge
    - Mobile money: SMS/USSD verification
    - Digital wallets: OAuth or API verification
    """
    try:
        # Verify payment method belongs to user
        existing_method = await payment_methods_service.get_payment_method_by_id(
            payment_method_id=payment_method_id,
            user_id=current_user["user_id"]
        )
        
        if not existing_method:
            raise NotFoundError("Payment method not found")
        
        # Check if already verified
        if existing_method.status == PaymentMethodStatus.VERIFIED:
            return BaseResponse(
                success=True,
                message="Payment method is already verified",
                data=PaymentMethodVerificationResponse(
                    verification_id=f"existing_{payment_method_id}",
                    status="completed",
                    message="Payment method is already verified",
                    next_steps=[]
                )
            )
        
        # Initiate or complete verification
        verification_result = await payment_methods_service.verify_payment_method(
            payment_method_id=payment_method_id,
            user_id=current_user["user_id"],
            verification_data=verification_data
        )
        
        return BaseResponse(
            success=True,
            message="Verification process initiated successfully",
            data=verification_result
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify payment method: {str(e)}"
        )

@router.post(
    "/{payment_method_id}/set-default",
    response_model=BaseResponse,
    summary="Set Default Payment Method",
    description="Set a payment method as the default for transactions"
)
async def set_default_payment_method(
    payment_method_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Set a payment method as the default for transactions.
    
    This will:
    - Remove default status from other payment methods
    - Set the specified payment method as default
    - Require the payment method to be verified
    """
    try:
        # Verify payment method belongs to user and is verified
        existing_method = await payment_methods_service.get_payment_method_by_id(
            payment_method_id=payment_method_id,
            user_id=current_user["user_id"]
        )
        
        if not existing_method:
            raise NotFoundError("Payment method not found")
        
        if existing_method.status != PaymentMethodStatus.VERIFIED:
            raise ConflictError("Only verified payment methods can be set as default")
        
        # Set as default
        updated_method = await payment_methods_service.set_default_payment_method(
            payment_method_id=payment_method_id,
            user_id=current_user["user_id"]
        )
        
        return BaseResponse(
            success=True,
            message="Default payment method updated successfully",
            data=updated_method
        )
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set default payment method: {str(e)}"
        )

@router.get(
    "/types",
    response_model=BaseResponse,
    summary="Get Supported Payment Method Types",
    description="Get list of supported payment method types and their requirements"
)
async def get_supported_payment_types():
    """
    Get list of supported payment method types and their requirements.
    
    Returns information about:
    - Available payment method types
    - Required fields for each type
    - Validation rules
    - Supported countries/currencies
    """
    try:
        supported_types = await payment_methods_service.get_supported_payment_types()
        
        return BaseResponse(
            success=True,
            message="Supported payment types retrieved successfully",
            data=supported_types
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve supported payment types: {str(e)}"
        )
