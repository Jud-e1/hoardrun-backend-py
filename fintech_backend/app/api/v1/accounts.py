"""
Account management API endpoints - Plaid-based implementation.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Optional

from ...models.account import (
    StatementRequest, BalanceHistoryRequest,
    AccountListResponse, AccountResponse,
    AccountBalanceResponse, AccountStatementResponse, BalanceHistoryResponse,
    AccountOverviewResponse
)
from ...services.account_service import get_account_service
from ...core.exceptions import (
    ValidationError, NotFoundError, BusinessLogicError,
    UnauthorizedError
)
from ...utils.response import success_response
from ...config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("/", response_model=AccountListResponse)
async def list_accounts(
    user_id: str = Query(..., description="User ID to list accounts for"),
    account_type: Optional[str] = Query(None, description="Filter by account type"),
    status: Optional[str] = Query(None, description="Filter by account status")
):
    """
    List all Plaid accounts for a user with optional filtering.
    
    Returns a list of financial accounts from Plaid belonging to the user,
    with optional filtering by type or status.
    """
    try:
        logger.info(f"API: Listing Plaid accounts for user {user_id}")
        
        account_service = get_account_service()
        result = await account_service.list_user_accounts(
            user_id, 
            account_type=account_type,
            status=status
        )
        
        return success_response(
            data=result,
            message=f"Retrieved {result['total_count']} Plaid accounts successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str = Path(..., description="Plaid Account ID"),
    user_id: str = Query(..., description="User ID")
):
    """
    Get detailed information for a specific Plaid account.
    
    Returns comprehensive account details from Plaid including balance,
    account metadata, and connection information.
    """
    try:
        logger.info(f"API: Getting Plaid account details for {account_id}")
        
        account_service = get_account_service()
        account = await account_service.get_account_details(account_id, user_id)
        
        return success_response(
            data={"account": account},
            message="Plaid account details retrieved successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting account: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{account_id}/balance", response_model=AccountBalanceResponse)
async def get_account_balance(
    account_id: str = Path(..., description="Plaid Account ID"),
    user_id: str = Query(..., description="User ID")
):
    """
    Get current account balance information from Plaid.
    
    Returns real-time balance data from Plaid including available balance,
    current balance, and limit information.
    """
    try:
        logger.info(f"API: Getting balance for Plaid account {account_id}")
        
        account_service = get_account_service()
        result = await account_service.get_account_balance(account_id, user_id)
        
        return success_response(
            data=result,
            message="Plaid account balance retrieved successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting account balance: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{account_id}/statement", response_model=AccountStatementResponse)
async def generate_statement(
    account_id: str = Path(..., description="Plaid Account ID"),
    user_id: str = Query(..., description="User ID"),
    request: StatementRequest = ...
):
    """
    Generate account statement from Plaid transaction data.
    
    Creates a detailed statement with all Plaid transactions,
    opening/closing balances, and category summaries for the specified period.
    """
    try:
        logger.info(f"API: Generating statement for Plaid account {account_id}")
        
        account_service = get_account_service()
        result = await account_service.generate_statement(account_id, user_id, request)
        
        return success_response(
            data=result,
            message="Account statement generated successfully from Plaid data"
        )
        
    except NotFoundError as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating statement: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{account_id}/history", response_model=BalanceHistoryResponse)
async def get_balance_history(
    account_id: str = Path(..., description="Plaid Account ID"),
    user_id: str = Query(..., description="User ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    granularity: str = Query("daily", description="Data granularity (daily, weekly, monthly)")
):
    """
    Get account balance history from Plaid data.
    
    Returns historical balance data calculated from Plaid transactions
    with trend analysis and configurable time periods and granularity.
    """
    try:
        logger.info(f"API: Getting balance history for Plaid account {account_id}")
        
        account_service = get_account_service()
        request = BalanceHistoryRequest(days=days, granularity=granularity)
        result = await account_service.get_balance_history(account_id, user_id, request)
        
        return success_response(
            data=result,
            message="Balance history retrieved successfully from Plaid"
        )
        
    except NotFoundError as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting balance history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/overview", response_model=AccountOverviewResponse)
async def get_account_overview(
    user_id: str = Query(..., description="User ID")
):
    """
    Get comprehensive financial overview from Plaid accounts.
    
    Returns complete financial picture from Plaid including all accounts,
    net worth, cash flow analysis, and financial trends.
    """
    try:
        logger.info(f"API: Getting account overview for user {user_id}")
        
        account_service = get_account_service()
        result = await account_service.get_account_overview(user_id)
        
        return success_response(
            data=result,
            message="Account overview retrieved successfully from Plaid"
        )
        
    except NotFoundError as e:
        logger.error(f"User or accounts not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting account overview: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def accounts_health():
    """
    Health check endpoint for Plaid account service.
    
    Returns the operational status of the Plaid account management service.
    """
    try:
        return success_response(
            data={
                "service": "plaid_account_service",
                "status": "healthy",
                "version": "2.0.0",
                "provider": "Plaid"
            },
            message="Plaid account service is healthy"
        )
        
    except Exception as e:
        logger.error(f"Account service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


