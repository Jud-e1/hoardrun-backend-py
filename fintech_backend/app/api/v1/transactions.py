"""
Transaction management API endpoints - Plaid-based implementation.
"""

from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional
from datetime import datetime

from ..models.transaction import (
    TransactionListRequest, TransactionSearchRequest, TransactionUpdateRequest,
    TransactionCategorizeRequest, TransactionExportRequest,
    TransactionListResponse, TransactionResponse
)
from ..services.transaction_service import get_transaction_service
from ..core.exceptions import (
    ValidationError, NotFoundError, BusinessLogicError, UnauthorizedError
)
from ..utils.response import success_response
from ..config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("/", response_model=TransactionListResponse)
async def list_transactions(
    user_id: str = Query(..., description="User ID to list transactions for"),
    account_id: Optional[str] = Query(None, description="Filter by Plaid account ID"),
    start_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    min_amount: Optional[float] = Query(None, ge=0, description="Minimum amount filter"),
    max_amount: Optional[float] = Query(None, gt=0, description="Maximum amount filter"),
    search_query: Optional[str] = Query(None, description="Search in transaction names"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    sort_by: str = Query("transaction_date", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)")
):
    """
    List Plaid transactions with comprehensive filtering and pagination.
    
    Returns a paginated list of transactions from Plaid with summary statistics
    and supports extensive filtering options.
    """
    try:
        logger.info(f"API: Listing Plaid transactions for user {user_id}")
        
        # Parse dates if provided
        parsed_start_date = None
        parsed_end_date = None
        
        if start_date:
            try:
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=422, detail="Invalid start_date format. Use YYYY-MM-DD")
        
        if end_date:
            try:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=422, detail="Invalid end_date format. Use YYYY-MM-DD")
        
        # Create request object
        request = TransactionListRequest(
            account_id=account_id,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            min_amount=min_amount,
            max_amount=max_amount,
            search_query=search_query,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        transaction_service = get_transaction_service()
        result = await transaction_service.list_transactions(user_id, request)
        
        return success_response(
            data=result,
            message=f"Retrieved {result['total_count']} Plaid transactions"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str = Path(..., description="Plaid Transaction ID"),
    user_id: str = Query(..., description="User ID")
):
    """
    Get detailed information for a specific Plaid transaction.
    
    Returns comprehensive transaction details from Plaid including all
    metadata, merchant information, and categorization.
    """
    try:
        logger.info(f"API: Getting Plaid transaction details for {transaction_id}")
        
        transaction_service = get_transaction_service()
        transaction = await transaction_service.get_transaction_details(transaction_id, user_id)
        
        return success_response(
            data={"transaction": transaction},
            message="Plaid transaction details retrieved successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Transaction not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transaction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/search", response_model=dict)
async def search_transactions(
    user_id: str = Query(..., description="User ID"),
    request: TransactionSearchRequest = ...
):
    """
    Advanced search for Plaid transactions with fuzzy matching.
    
    Performs intelligent search across Plaid transaction data with
    fuzzy matching and search suggestions.
    """
    try:
        logger.info(f"API: Searching Plaid transactions for user {user_id}")
        
        transaction_service = get_transaction_service()
        result = await transaction_service.search_transactions(user_id, request)
        
        return success_response(
            data=result,
            message=f"Found {result['total_matches']} matching Plaid transactions"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: str = Path(..., description="Plaid Transaction ID"),
    user_id: str = Query(..., description="User ID"),
    request: TransactionUpdateRequest = ...
):
    """
    Update Plaid transaction metadata (user-editable fields only).
    
    Note: Plaid transaction data itself cannot be modified.
    This endpoint updates custom metadata like notes, tags, and custom categories.
    """
    try:
        logger.info(f"API: Updating Plaid transaction metadata for {transaction_id}")
        
        transaction_service = get_transaction_service()
        transaction = await transaction_service.update_transaction(transaction_id, user_id, request)
        
        return success_response(
            data={"transaction": transaction},
            message="Plaid transaction metadata updated successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Transaction not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessLogicError as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating transaction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/account/{account_id}", response_model=TransactionListResponse)
async def get_account_transactions(
    account_id: str = Path(..., description="Plaid Account ID"),
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """
    Get Plaid transactions for a specific account.
    
    Returns all Plaid transactions for the specified account with pagination.
    """
    try:
        logger.info(f"API: Getting Plaid transactions for account {account_id}")
        
        request = TransactionListRequest(
            account_id=account_id,
            limit=limit,
            offset=offset,
            sort_by="transaction_date",
            sort_order="desc"
        )
        
        transaction_service = get_transaction_service()
        result = await transaction_service.list_transactions(user_id, request)
        
        return success_response(
            data=result,
            message=f"Retrieved {result['total_count']} Plaid transactions for account"
        )
        
    except NotFoundError as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting account transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/analytics", response_model=dict)
async def get_transaction_analytics(
    user_id: str = Query(..., description="User ID"),
    account_id: Optional[str] = Query(None, description="Filter by Plaid account ID"),
    days: int = Query(90, ge=1, le=365, description="Analysis period in days")
):
    """
    Get comprehensive transaction analytics from Plaid data.
    
    Returns detailed analytics including spending patterns, category breakdowns,
    and trends calculated from Plaid transaction data.
    """
    try:
        logger.info(f"API: Getting Plaid transaction analytics for user {user_id}")
        
        transaction_service = get_transaction_service()
        result = await transaction_service.get_transaction_analytics(user_id, account_id, days)
        
        return success_response(
            data=result,
            message="Plaid transaction analytics retrieved successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"User or account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transaction analytics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/recent", response_model=TransactionListResponse)
async def get_recent_transactions(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(10, ge=1, le=100, description="Number of recent transactions"),
    account_id: Optional[str] = Query(None, description="Filter by Plaid account ID")
):
    """
    Get most recent Plaid transactions for quick access.
    
    Returns the most recent Plaid transactions ordered by date
    for dashboard or quick reference purposes.
    """
    try:
        logger.info(f"API: Getting recent Plaid transactions for user {user_id}")
        
        transaction_service = get_transaction_service()
        transactions = await transaction_service.get_recent_transactions(
            user_id, limit, account_id
        )
        
        result = {
            "transactions": transactions,
            "total_count": len(transactions),
            "has_more": False
        }
        
        return success_response(
            data=result,
            message=f"Retrieved {len(transactions)} recent Plaid transactions"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting recent transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/export", response_model=dict)
async def export_transactions(
    user_id: str = Query(..., description="User ID"),
    request: TransactionExportRequest = ...
):
    """
    Export Plaid transactions to various formats.
    
    Generates downloadable export of Plaid transaction data in
    CSV, Excel, or PDF format.
    """
    try:
        logger.info(f"API: Exporting Plaid transactions for user {user_id}")
        
        transaction_service = get_transaction_service()
        result = await transaction_service.export_transactions(user_id, request)
        
        return success_response(
            data=result,
            message="Plaid transaction export created successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def transactions_health():
    """
    Health check endpoint for Plaid transaction service.
    
    Returns the operational status of the Plaid transaction management service.
    """
    try:
        return success_response(
            data={
                "service": "plaid_transaction_service",
                "status": "healthy",
                "version": "2.0.0",
                "provider": "Plaid"
            },
            message="Plaid transaction service is healthy"
        )
        
    except Exception as e:
        logger.error(f"Transaction service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
