"""
Mobile Money API endpoints for mobile payment integration.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Body, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, List
import asyncio
from datetime import datetime
from decimal import Decimal

from ..models.mobile_money import (
    MobileMoneyTransferRequest, MobileMoneyReceiveRequest, MobileMoneyAccountRequest,
    MobileMoneyDepositRequest, MobileMoneyTransferResponse, MobileMoneyReceiveResponse,
    MobileMoneyProvidersResponse, MobileMoneyAccountResponse, MobileMoneyTransactionListResponse,
    MobileMoneyProvider, TransactionType, TransactionStatus, Currency,
    MobileMoneyTransactionFilter, MobileMoneyStats, MobileMoneyFeeCalculation
)
from ..services.mobile_money_service import MobileMoneyService
from ..database.config import get_db
from ..core.exceptions import (
    ValidationException, AuthenticationException, AuthorizationException,
    UserNotFoundException, NotFoundError, BusinessLogicError
)
from ..utils.response import success_response
from ..config.logging import get_logger

logger = get_logger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/momo", tags=["Mobile Money"])


def get_mobile_money_service():
    """Dependency to get mobile money service instance"""
    return MobileMoneyService()


@router.post("/send", response_model=MobileMoneyTransferResponse)
async def send_mobile_money(
    request: MobileMoneyTransferRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    momo_service: MobileMoneyService = Depends(get_mobile_money_service)
):
    """
    Send money via mobile money.
    
    Initiates a mobile money transfer to the specified recipient.
    """
    try:
        logger.info(f"API: Sending mobile money - {request.provider} - {request.amount} {request.currency}")
        
        token = credentials.credentials
        transaction = await momo_service.send_money(token, request, db)
        
        return success_response(
            data={"transaction": transaction},
            message="Mobile money transfer initiated successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending mobile money: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/receive", response_model=MobileMoneyReceiveResponse)
async def receive_mobile_money(
    request: MobileMoneyReceiveRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    momo_service: MobileMoneyService = Depends(get_mobile_money_service)
):
    """
    Receive money via mobile money.
    
    Initiates a mobile money collection request from the specified sender.
    """
    try:
        logger.info(f"API: Receiving mobile money - {request.provider} - {request.amount} {request.currency}")
        
        token = credentials.credentials
        transaction = await momo_service.receive_money(token, request, db)
        
        return success_response(
            data={"transaction": transaction},
            message="Mobile money collection request initiated successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error receiving mobile money: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/providers", response_model=MobileMoneyProvidersResponse)
async def get_mobile_money_providers(
    country: Optional[str] = Query(None, description="Filter by country code"),
    currency: Optional[Currency] = Query(None, description="Filter by currency"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    momo_service: MobileMoneyService = Depends(get_mobile_money_service)
):
    """
    Get available mobile money providers.
    
    Returns a list of available mobile money providers with their details.
    """
    try:
        logger.info("API: Getting mobile money providers")
        
        token = credentials.credentials
        providers = await momo_service.get_providers(token, country, currency, is_active, db)
        
        return success_response(
            data={"providers": providers},
            message="Mobile money providers retrieved successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting providers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/verify", response_model=MobileMoneyAccountResponse)
async def verify_mobile_money_account(
    request: MobileMoneyAccountRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    momo_service: MobileMoneyService = Depends(get_mobile_money_service)
):
    """
    Verify mobile money account.
    
    Verifies the existence and validity of a mobile money account.
    """
    try:
        logger.info(f"API: Verifying mobile money account - {request.provider}")
        
        token = credentials.credentials
        account = await momo_service.verify_account(token, request, db)
        
        return success_response(
            data={"account": account},
            message="Mobile money account verified successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except NotFoundError as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error verifying account: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/deposit", response_model=MobileMoneyTransferResponse)
async def deposit_to_mobile_money(
    request: MobileMoneyDepositRequest = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    momo_service: MobileMoneyService = Depends(get_mobile_money_service)
):
    """
    Deposit money to mobile money account.
    
    Initiates a deposit transaction to the user's mobile money account.
    """
    try:
        logger.info(f"API: Depositing to mobile money - {request.provider} - {request.amount} {request.currency}")
        
        token = credentials.credentials
        transaction = await momo_service.deposit_money(token, request, db)
        
        return success_response(
            data={"transaction": transaction},
            message="Mobile money deposit initiated successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error depositing to mobile money: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/transactions", response_model=MobileMoneyTransactionListResponse)
async def get_mobile_money_transactions(
    provider: Optional[MobileMoneyProvider] = Query(None, description="Filter by provider"),
    transaction_type: Optional[TransactionType] = Query(None, description="Filter by type"),
    status: Optional[TransactionStatus] = Query(None, description="Filter by status"),
    currency: Optional[Currency] = Query(None, description="Filter by currency"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    momo_service: MobileMoneyService = Depends(get_mobile_money_service)
):
    """
    Get mobile money transactions.
    
    Returns a paginated list of the user's mobile money transactions.
    """
    try:
        logger.info("API: Getting mobile money transactions")
        
        token = credentials.credentials
        filter_params = MobileMoneyTransactionFilter(
            provider=provider,
            transaction_type=transaction_type,
            status=status,
            currency=currency,
            page=page,
            per_page=per_page
        )
        
        result = await momo_service.get_transactions(token, filter_params, db)
        
        return MobileMoneyTransactionListResponse(
            success=True,
            message="Mobile money transactions retrieved successfully",
            data={"transactions": result["transactions"]},
            total=result["total"],
            page=result["page"],
            per_page=result["per_page"]
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/transactions/{transaction_id}", response_model=dict)
async def get_mobile_money_transaction(
    transaction_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    momo_service: MobileMoneyService = Depends(get_mobile_money_service)
):
    """
    Get a specific mobile money transaction.
    
    Returns detailed information about a specific transaction.
    """
    try:
        logger.info(f"API: Getting mobile money transaction - {transaction_id}")
        
        token = credentials.credentials
        transaction = await momo_service.get_transaction(token, transaction_id, db)
        
        return success_response(
            data={"transaction": transaction},
            message="Mobile money transaction retrieved successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except NotFoundError as e:
        logger.error(f"Transaction not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transaction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/transactions/{transaction_id}/cancel", response_model=dict)
async def cancel_mobile_money_transaction(
    transaction_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    momo_service: MobileMoneyService = Depends(get_mobile_money_service)
):
    """
    Cancel a mobile money transaction.
    
    Cancels a pending mobile money transaction.
    """
    try:
        logger.info(f"API: Cancelling mobile money transaction - {transaction_id}")
        
        token = credentials.credentials
        result = await momo_service.cancel_transaction(token, transaction_id, db)
        
        return success_response(
            data=result,
            message="Mobile money transaction cancelled successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except NotFoundError as e:
        logger.error(f"Transaction not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error cancelling transaction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/accounts", response_model=dict)
async def get_mobile_money_accounts(
    provider: Optional[MobileMoneyProvider] = Query(None, description="Filter by provider"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    momo_service: MobileMoneyService = Depends(get_mobile_money_service)
):
    """
    Get user's mobile money accounts.
    
    Returns a list of the user's registered mobile money accounts.
    """
    try:
        logger.info("API: Getting mobile money accounts")
        
        token = credentials.credentials
        accounts = await momo_service.get_user_accounts(token, provider, is_verified, is_active, db)
        
        return success_response(
            data={"accounts": accounts},
            message="Mobile money accounts retrieved successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting accounts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/fees/calculate", response_model=dict)
async def calculate_mobile_money_fees(
    provider: MobileMoneyProvider = Query(..., description="Mobile money provider"),
    amount: Decimal = Query(..., gt=0, description="Transaction amount"),
    currency: Currency = Query(..., description="Currency code"),
    transaction_type: TransactionType = Query(..., description="Transaction type"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    momo_service: MobileMoneyService = Depends(get_mobile_money_service)
):
    """
    Calculate mobile money transaction fees.
    
    Returns the calculated fees for a mobile money transaction.
    """
    try:
        logger.info(f"API: Calculating mobile money fees - {provider} - {amount} {currency}")
        
        token = credentials.credentials
        fee_calculation = await momo_service.calculate_fees(token, provider, amount, currency, transaction_type, db)
        
        return success_response(
            data={"fee_calculation": fee_calculation},
            message="Mobile money fees calculated successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating fees: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats", response_model=dict)
async def get_mobile_money_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    momo_service: MobileMoneyService = Depends(get_mobile_money_service)
):
    """
    Get mobile money statistics.
    
    Returns statistical information about the user's mobile money transactions.
    """
    try:
        logger.info("API: Getting mobile money statistics")
        
        token = credentials.credentials
        stats = await momo_service.get_transaction_stats(token, db)
        
        return success_response(
            data={"stats": stats},
            message="Mobile money statistics retrieved successfully"
        )
        
    except AuthenticationException as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def mobile_money_service_health():
    """
    Health check endpoint for mobile money service.
    
    Returns the operational status of the mobile money service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time
        
        return success_response(
            data={
                "service": "mobile_money_service",
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0",
                "providers_available": 8,
                "currencies_supported": 8
            },
            message="Mobile money service is healthy"
        )
        
    except Exception as e:
        logger.error(f"Mobile money service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
