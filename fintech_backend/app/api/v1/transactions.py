"""
Transaction management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import asyncio

from app.models.transaction import (
    TransactionType, TransactionStatus, TransactionCreateRequest, TransactionFilters,
    TransactionListResponse, TransactionResponse
)
from app.services.database_transaction_service import DatabaseTransactionService
from app.database.config import get_db
from app.core.exceptions import (
    ValidationException, AccountNotFoundException, BusinessRuleViolationException, FintechException
)
from app.utils.response import success_response
from app.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


def get_transaction_service(db: Session = Depends(get_db)):
    """Dependency to get transaction service instance"""
    return DatabaseTransactionService(db)


@router.get("/", response_model=TransactionListResponse)
async def list_transactions(
    user_id: str = Query(..., description="User ID to list transactions for"),
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    min_amount: Optional[float] = Query(None, ge=0, description="Minimum amount filter"),
    max_amount: Optional[float] = Query(None, gt=0, description="Maximum amount filter"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
    transaction_service: DatabaseTransactionService = Depends(get_transaction_service)
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
        
        # Create filters object
        filters = TransactionFilters(
            account_id=account_id,
            transaction_type=transaction_type,
            status=status,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            min_amount=min_amount,
            max_amount=max_amount,
            limit=limit,
            offset=offset
        )
        
        transactions = transaction_service.get_user_transactions(user_id, filters, db)
        
        # Create a basic summary for the response
        from app.models.transaction import TransactionSummary
        from datetime import date
        from decimal import Decimal
        
        summary = TransactionSummary(
            period_start=parsed_start_date or date.today(),
            period_end=parsed_end_date or date.today(),
            total_transactions=len(transactions),
            total_amount=sum(t.amount for t in transactions) if transactions else Decimal("0"),
            total_credits=sum(t.amount for t in transactions if t.amount > 0) if transactions else Decimal("0"),
            total_debits=sum(abs(t.amount) for t in transactions if t.amount < 0) if transactions else Decimal("0"),
            average_transaction=sum(t.amount for t in transactions) / len(transactions) if transactions else Decimal("0"),
            largest_transaction=max(t.amount for t in transactions) if transactions else Decimal("0"),
            by_category={},
            by_merchant={}
        )
        
        # Return the response directly without success_response wrapper
        return TransactionListResponse(
            success=True,
            message=f"Retrieved {len(transactions)} transactions",
            status_code=200,
            data=None,
            transactions=transactions,
            total_count=len(transactions),
            summary=summary,
            has_more=len(transactions) == limit
        )
        
    except AccountNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str = Path(..., description="Transaction ID"),
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db),
    transaction_service: DatabaseTransactionService = Depends(get_transaction_service)
):
    """
    Get detailed information for a specific transaction.
    
    Returns comprehensive transaction details including all
    metadata, categorization, and status information.
    """
    try:
        logger.info(f"API: Getting transaction details for {transaction_id}")
        
        transaction = transaction_service.get_transaction_by_id(transaction_id, user_id, db)
        
        return success_response(
            data={"transaction": transaction},
            message="Transaction details retrieved successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Transaction not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transaction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/", response_model=TransactionResponse)
async def create_transaction(
    user_id: str = Query(..., description="User ID"),
    request: TransactionCreateRequest = ...,
    db: Session = Depends(get_db),
    transaction_service: DatabaseTransactionService = Depends(get_transaction_service)
):
    """
    Create a new transaction.
    
    Creates a new transaction and updates the associated account balance.
    """
    try:
        logger.info(f"API: Creating transaction for user {user_id}")
        
        transaction = transaction_service.create_transaction(user_id, request, db)
        
        return success_response(
            data={"transaction": transaction},
            message="Transaction created successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except BusinessRuleViolationException as e:
        logger.error(f"Business logic error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating transaction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/account/{account_id}", response_model=TransactionListResponse)
async def get_account_transactions(
    account_id: str = Path(..., description="Account ID"),
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
    transaction_service: DatabaseTransactionService = Depends(get_transaction_service)
):
    """
    Get transactions for a specific account.
    
    Returns all transactions for the specified account with pagination.
    """
    try:
        logger.info(f"API: Getting transactions for account {account_id}")
        
        transactions = transaction_service.get_account_transactions(account_id, user_id, limit, offset, db)
        
        result = {
            "transactions": transactions,
            "total_count": len(transactions),
            "has_more": len(transactions) == limit
        }
        
        return success_response(
            data=result,
            message=f"Retrieved {len(transactions)} transactions for account"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except FintechException as e:
        logger.error(f"Unauthorized access: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting account transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/summary", response_model=dict)
async def get_transaction_summary(
    user_id: str = Query(..., description="User ID"),
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    db: Session = Depends(get_db),
    transaction_service: DatabaseTransactionService = Depends(get_transaction_service)
):
    """
    Get transaction summary statistics.
    
    Returns comprehensive summary including totals, counts, and breakdowns.
    """
    try:
        logger.info(f"API: Getting transaction summary for user {user_id}")
        
        summary = transaction_service.get_transaction_summary(user_id, account_id, db)
        
        return success_response(
            data=summary,
            message="Transaction summary retrieved successfully"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"User or account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transaction summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/recent", response_model=TransactionListResponse)
async def get_recent_transactions(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(10, ge=1, le=100, description="Number of recent transactions"),
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    db: Session = Depends(get_db),
    transaction_service: DatabaseTransactionService = Depends(get_transaction_service)
):
    """
    Get most recent transactions for quick access.
    
    Returns the most recent transactions ordered by date
    for dashboard or quick reference purposes.
    """
    try:
        logger.info(f"API: Getting recent transactions for user {user_id}")
        
        # Create filters for recent transactions
        filters = TransactionFilters(
            account_id=account_id,
            limit=limit,
            offset=0
        )
        
        transactions = transaction_service.get_user_transactions(user_id, filters, db)
        
        result = {
            "transactions": transactions,
            "total_count": len(transactions),
            "has_more": False
        }
        
        return success_response(
            data=result,
            message=f"Retrieved {len(transactions)} recent transactions"
        )
        
    except AccountNotFoundException as e:
        logger.error(f"User not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting recent transactions: {e}")
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
