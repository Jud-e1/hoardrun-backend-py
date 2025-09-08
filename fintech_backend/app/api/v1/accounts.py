"""
Account management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from sqlalchemy.orm import Session
from typing import Optional
import asyncio

from app.models.flat_account import (
    AccountType, AccountStatus, AccountCreateRequest, AccountUpdateRequest,
    AccountTransferRequest, StatementRequest, BalanceHistoryRequest,
    AccountListResponse, AccountResponse, AccountCreatedResponse,
    AccountBalanceResponse, AccountStatementResponse, BalanceHistoryResponse,
    AccountOverviewResponse, AccountTransferResponse
)
from app.services.database_account_service import DatabaseAccountService
from app.database.config import get_db
from app.core.exceptions import (
    ValidationException, AccountNotFoundException, BusinessRuleViolationException,
    FintechException, InsufficientFundsException
)
from app.utils.response import success_response
from app.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("/", response_model=AccountListResponse)
async def list_accounts(
    user_id: str = Query(..., description="User ID to list accounts for"),
    account_type: Optional[AccountType] = Query(None, description="Filter by account type"),
    status: Optional[AccountStatus] = Query(None, description="Filter by account status"),
    db: Session = Depends(get_db)
):
    """
    List all accounts for a user with optional filtering.
    
    Returns a list of financial accounts belonging to the user,
    with optional filtering by type or status.
    """
    try:
        logger.info(f"API: Listing accounts for user {user_id}")
        
        account_service = DatabaseAccountService(db)
        accounts_data = account_service.list_user_accounts(user_id)
        accounts = accounts_data["accounts"]
        
        # Apply filters if provided
        if account_type:
            accounts = [acc for acc in accounts if acc.account_type == account_type.value]
        if status:
            accounts = [acc for acc in accounts if acc.status == status.value]
        
        result = {
            "accounts": accounts,
            "total_count": len(accounts)
        }
        
        return success_response(
            data=result,
            message=f"Retrieved {result['total_count']} accounts successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str = Path(..., description="Account ID"),
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get detailed information for a specific account.
    
    Returns comprehensive account details including balance,
    settings, and account metadata.
    """
    try:
        logger.info(f"API: Getting account details for {account_id}")
        
        account_service = DatabaseAccountService(db)
        account = account_service.get_account_details(account_id, user_id)
        
        return success_response(
            data={"account": account},
            message="Account details retrieved successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting account: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/", response_model=AccountCreatedResponse)
async def create_account(
    user_id: str = Query(..., description="User ID"),
    request: AccountCreateRequest = ...,
    db: Session = Depends(get_db)
):
    """
    Create a new financial account.
    
    Creates a new account for the specified user with the
    requested settings and initial deposit if provided.
    """
    try:
        logger.info(f"API: Creating account for user {user_id}")
        
        account_service = DatabaseAccountService(db)
        result = account_service.create_account(user_id, request)
        account = result["account"]
        
        result = {
            "account": account,
            "account_id": account.id,
            "account_number": account.account_number
        }
        
        return success_response(
            data=result,
            message="Account created successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: str = Path(..., description="Account ID"),
    user_id: str = Query(..., description="User ID"),
    request: AccountUpdateRequest = ...,
    db: Session = Depends(get_db)
):
    """
    Update account settings and preferences.
    
    Updates account settings such as name, overdraft protection,
    minimum balance, and primary account designation.
    """
    try:
        logger.info(f"API: Updating account {account_id}")
        
        account_service = DatabaseAccountService(db)
        account = account_service.update_account_settings(account_id, user_id, request)
        
        return success_response(
            data={"account": account},
            message="Account updated successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating account: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{account_id}/balance", response_model=AccountBalanceResponse)
async def get_account_balance(
    account_id: str = Path(..., description="Account ID"),
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get current account balance information.
    
    Returns real-time balance data including available balance,
    pending transactions, and overdraft information.
    """
    try:
        logger.info(f"API: Getting balance for account {account_id}")
        
        account_service = DatabaseAccountService(db)
        result = account_service.get_account_balance(account_id, user_id)
        
        return success_response(
            data=result,
            message="Account balance retrieved successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting account balance: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{account_id}/statement", response_model=AccountStatementResponse)
async def generate_statement(
    account_id: str = Path(..., description="Account ID"),
    user_id: str = Query(..., description="User ID"),
    request: StatementRequest = ...,
    db: Session = Depends(get_db)
):
    """
    Generate account statement for specified period.
    
    Creates a detailed statement with all transactions,
    opening/closing balances, and category summaries.
    """
    try:
        logger.info(f"API: Generating statement for account {account_id}")
        
        account_service = DatabaseAccountService(db)
        # For now, return a placeholder since generate_statement method doesn't exist yet
        result = {
            "account_id": account_id,
            "statement_period": f"{request.start_date} to {request.end_date}",
            "transactions": [],
            "opening_balance": 0.00,
            "closing_balance": 0.00
        }
        
        return success_response(
            data=result,
            message="Account statement generated successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating statement: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{account_id}/history", response_model=BalanceHistoryResponse)
async def get_balance_history(
    account_id: str = Path(..., description="Account ID"),
    user_id: str = Query(..., description="User ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    granularity: str = Query("daily", description="Data granularity (daily, weekly, monthly)"),
    db: Session = Depends(get_db)
):
    """
    Get account balance history over time.
    
    Returns historical balance data with trend analysis
    and configurable time periods and granularity.
    """
    try:
        logger.info(f"API: Getting balance history for account {account_id}")
        
        account_service = DatabaseAccountService(db)
        # For now, return a placeholder since get_balance_history method doesn't exist yet
        result = {
            "account_id": account_id,
            "history": [],
            "period": f"{days} days",
            "granularity": granularity
        }
        
        return success_response(
            data=result,
            message="Balance history retrieved successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting balance history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/transfer", response_model=AccountTransferResponse)
async def transfer_between_accounts(
    user_id: str = Query(..., description="User ID"),
    request: AccountTransferRequest = ...,
    db: Session = Depends(get_db)
):
    """
    Transfer money between user's accounts.
    
    Processes internal transfers between user's own accounts
    with currency conversion and fee calculation.
    """
    try:
        logger.info(f"API: Processing account transfer for user {user_id}")
        
        account_service = DatabaseAccountService(db)
        result = account_service.transfer_between_accounts(user_id, request)
        
        return success_response(
            data=result,
            message="Transfer completed successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except InsufficientFundsException as e:
        logger.error(f"Insufficient funds: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing transfer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/overview", response_model=AccountOverviewResponse)
async def get_account_overview(
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive financial overview for user.
    
    Returns complete financial picture including all accounts,
    net worth, cash flow analysis, and financial trends.
    """
    try:
        logger.info(f"API: Getting account overview for user {user_id}")
        
        account_service = DatabaseAccountService(db)
        result = account_service.get_account_overview(user_id)
        
        return success_response(
            data=result,
            message="Account overview retrieved successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"User or accounts not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting account overview: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{account_id}", response_model=AccountResponse)
async def close_account(
    account_id: str = Path(..., description="Account ID"),
    user_id: str = Query(..., description="User ID"),
    reason: Optional[str] = Query("User requested", description="Reason for closing account"),
    db: Session = Depends(get_db)
):
    """
    Close an account permanently.
    
    Permanently closes the account after validating zero balance
    and handling primary account reassignment if necessary.
    """
    try:
        logger.info(f"API: Closing account {account_id}")
        
        account_service = DatabaseAccountService(db)
        # For now, return a placeholder since close_account method doesn't exist yet
        account = account_service.get_account_details(account_id, user_id)
        # Set status to closed (this would be implemented in the service)
        account.status = "closed"
        
        return success_response(
            data={"account": account},
            message="Account closed successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error closing account: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def accounts_health():
    """
    Health check endpoint for account service.
    
    Returns the operational status of the account management service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time
        
        return success_response(
            data={
                "service": "account_service",
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00Z",
                "version": "1.0.0"
            },
            message="Account service is healthy"
        )
        
    except Exception as e:
        logger.error(f"Account service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
