"""
Transaction management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import asyncio

from app.models.transaction import (
    TransactionType, TransactionStatus, TransactionDirection, MerchantCategory,
    PaymentMethod, TransactionListRequest, TransactionSearchRequest,
    TransactionUpdateRequest, TransactionDisputeRequest, TransactionCategorizeRequest,
    TransactionExportRequest, TransactionListResponse, TransactionResponse,
    TransactionSearchResponse, TransactionAnalyticsResponse, TransactionExportResponse,
    DisputeResponse, BulkUpdateResponse, TransactionCategoryStats
)
from app.services.transaction_service import TransactionService, get_transaction_service
from app.core.exceptions import (
    ValidationError, NotFoundError, BusinessLogicError, UnauthorizedError
)
from app.utils.response import success_response
from app.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("/", response_model=TransactionListResponse)
async def list_transactions(
    user_id: str = Query(..., description="User ID to list transactions for"),
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    transaction_type: Optional[TransactionType] = Query(None, description="Filter by transaction type"),
    status: Optional[TransactionStatus] = Query(None, description="Filter by status"),
    direction: Optional[TransactionDirection] = Query(None, description="Filter by direction"),
    merchant_category: Optional[MerchantCategory] = Query(None, description="Filter by merchant category"),
    payment_method: Optional[PaymentMethod] = Query(None, description="Filter by payment method"),
    start_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    min_amount: Optional[float] = Query(None, ge=0, description="Minimum amount filter"),
    max_amount: Optional[float] = Query(None, gt=0, description="Maximum amount filter"),
    search_query: Optional[str] = Query(None, description="Search in description or merchant name"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    sort_by: str = Query("transaction_date", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    List transactions with comprehensive filtering and pagination.
    
    Returns a paginated list of transactions with summary statistics
    and supports extensive filtering options.
    """
    try:
        logger.info(f"API: Listing transactions for user {user_id}")
        
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
            transaction_type=transaction_type,
            status=status,
            direction=direction,
            merchant_category=merchant_category,
            payment_method=payment_method,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            min_amount=Decimal(str(min_amount)) if min_amount is not None else None,
            max_amount=Decimal(str(max_amount)) if max_amount is not None else None,
            search_query=search_query,
            tags=tags,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        result = await transaction_service.list_transactions(user_id, request)
        
        return success_response(
            data=result,
            message=f"Retrieved {len(result['transactions'])} transactions"
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
    transaction_id: str = Path(..., description="Transaction ID"),
    user_id: str = Query(..., description="User ID"),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    Get detailed information for a specific transaction.
    
    Returns comprehensive transaction details including all
    metadata, categorization, and status information.
    """
    try:
        logger.info(f"API: Getting transaction details for {transaction_id}")
        
        transaction = await transaction_service.get_transaction_details(transaction_id, user_id)
        
        return success_response(
            data={"transaction": transaction},
            message="Transaction details retrieved successfully"
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


@router.post("/search", response_model=TransactionSearchResponse)
async def search_transactions(
    user_id: str = Query(..., description="User ID"),
    request: TransactionSearchRequest = ...,
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    Advanced search for transactions with fuzzy matching.
    
    Performs intelligent search across transaction fields with
    optional fuzzy matching and additional filtering.
    """
    try:
        logger.info(f"API: Searching transactions for user {user_id}")
        
        result = await transaction_service.search_transactions(user_id, request)
        
        return success_response(
            data=result,
            message=f"Found {result['total_matches']} matching transactions"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: str = Path(..., description="Transaction ID"),
    user_id: str = Query(..., description="User ID"),
    request: TransactionUpdateRequest = ...,
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    Update transaction details (user-editable fields only).
    
    Updates user-controllable transaction fields such as
    description, category, tags, and personal notes.
    """
    try:
        logger.info(f"API: Updating transaction {transaction_id}")
        
        transaction = await transaction_service.update_transaction(transaction_id, user_id, request)
        
        return success_response(
            data={"transaction": transaction},
            message="Transaction updated successfully"
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
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating transaction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/categorize", response_model=BulkUpdateResponse)
async def categorize_transactions(
    user_id: str = Query(..., description="User ID"),
    request: TransactionCategorizeRequest = ...,
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    Batch categorize multiple transactions.
    
    Updates the merchant category for multiple transactions
    with optional automatic categorization of similar transactions.
    """
    try:
        logger.info(f"API: Bulk categorizing transactions for user {user_id}")
        
        result = await transaction_service.categorize_transactions(user_id, request)
        
        return success_response(
            data=result,
            message=f"Categorized {result['updated_count']} transactions successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"Transaction not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error categorizing transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{transaction_id}/dispute", response_model=DisputeResponse)
async def dispute_transaction(
    transaction_id: str = Path(..., description="Transaction ID"),
    user_id: str = Query(..., description="User ID"),
    request: TransactionDisputeRequest = ...,
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    Initiate a dispute for a transaction.
    
    Creates a dispute case for unauthorized or incorrect transactions
    within the allowed dispute window.
    """
    try:
        logger.info(f"API: Initiating dispute for transaction {transaction_id}")
        
        result = await transaction_service.dispute_transaction(transaction_id, user_id, request)
        
        return success_response(
            data=result,
            message="Dispute initiated successfully"
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
        logger.error(f"Error initiating dispute: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/analytics", response_model=TransactionAnalyticsResponse)
async def get_transaction_analytics(
    user_id: str = Query(..., description="User ID"),
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    days: int = Query(90, ge=1, le=365, description="Analysis period in days"),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    Get comprehensive transaction analytics.
    
    Returns detailed analytics including spending patterns,
    category breakdowns, trends, and merchant analysis.
    """
    try:
        logger.info(f"API: Getting transaction analytics for user {user_id}")
        
        result = await transaction_service.get_transaction_analytics(user_id, account_id, days)
        
        return success_response(
            data=result,
            message="Transaction analytics retrieved successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"User or account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transaction analytics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/export", response_model=TransactionExportResponse)
async def export_transactions(
    user_id: str = Query(..., description="User ID"),
    request: TransactionExportRequest = ...,
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    Export transactions to various formats.
    
    Creates an export job and returns download information
    for transactions in CSV, JSON, or PDF format.
    """
    try:
        logger.info(f"API: Exporting transactions for user {user_id}")
        
        result = await transaction_service.export_transactions(user_id, request)
        
        return success_response(
            data=result,
            message="Export created successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/recent", response_model=TransactionListResponse)
async def get_recent_transactions(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(10, ge=1, le=100, description="Number of recent transactions"),
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    Get most recent transactions for quick access.
    
    Returns the most recent transactions ordered by date
    for dashboard or quick reference purposes.
    """
    try:
        logger.info(f"API: Getting recent transactions for user {user_id}")
        
        transactions = await transaction_service.get_recent_transactions(user_id, limit, account_id)
        
        # Create minimal summary for recent transactions
        total_amount = sum(abs(t.amount) for t in transactions)
        credits = sum(t.amount for t in transactions if t.amount > 0)
        debits = abs(sum(t.amount for t in transactions if t.amount < 0))
        
        from app.models.transaction import TransactionSummary
        summary = TransactionSummary(
            period_start=min(t.transaction_date.date() for t in transactions) if transactions else datetime.now().date(),
            period_end=max(t.transaction_date.date() for t in transactions) if transactions else datetime.now().date(),
            total_transactions=len(transactions),
            total_amount=total_amount,
            total_credits=credits,
            total_debits=debits
        )
        
        return success_response(
            data={
                "transactions": transactions,
                "total_count": len(transactions),
                "summary": summary,
                "has_more": False
            },
            message=f"Retrieved {len(transactions)} recent transactions"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting recent transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/categories/spending", response_model=List[TransactionCategoryStats])
async def get_spending_by_category(
    user_id: str = Query(..., description="User ID"),
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    days: int = Query(30, ge=1, le=365, description="Analysis period in days"),
    transaction_service: TransactionService = Depends(get_transaction_service)
):
    """
    Get spending breakdown by merchant category.
    
    Returns detailed statistics for each spending category
    including amounts, percentages, and transaction counts.
    """
    try:
        logger.info(f"API: Getting spending by category for user {user_id}")
        
        category_stats = await transaction_service.get_spending_by_category(user_id, account_id, days)
        
        return success_response(
            data=category_stats,
            message="Category spending statistics retrieved successfully"
        )
        
    except NotFoundError as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting category spending: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=dict)
async def transactions_health():
    """
    Health check endpoint for transaction service.
    
    Returns the operational status of the transaction management service.
    """
    try:
        # Simulate service checks
        await asyncio.sleep(0.01)  # Mock processing time
        
        return success_response(
            data={
                "service": "transaction_service",
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00Z",
                "version": "1.0.0"
            },
            message="Transaction service is healthy"
        )
        
    except Exception as e:
        logger.error(f"Transaction service health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
